import logging
import uuid
from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.autolabels.constants import AutoLabelProgress, PromotionItemOutcome
from src.autolabels.exceptions import EnqueueFailedException
from src.autolabels.models import AutoLabel, LabelPromotionJob, LabelPromotionJobItem
from src.autolabels.promotions.processing import process_promotion_job
from src.autolabels.promotions.sweeper import (
    PENDING_PROMOTION_GRACE_PERIOD,
    PromotionSweepResult,
    sweep_stale_promotions,
)
from src.labels.models import Label, LabelData, LabelGroup
from test_support.autolabels import RecordingPromotionDispatcher
from test_support.test_data.scenarios import DatabaseScenario
from tests.autolabels.test_promotion_processing import _add_autolabelled_chapters, _label_data_count, _outcomes


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.user_name}, timedelta(minutes=30))}"}


def _add_label_group(db: Session, scenario: DatabaseScenario, name: str) -> uuid.UUID:
    group = LabelGroup(label_group_name=name, novel_id=scenario.novels["novel"].novel_id)
    db.add(group)
    db.flush()
    return group.label_group_id


def _create_promotion_job(
    db: Session,
    scenario: DatabaseScenario,
    *,
    label_group_id: uuid.UUID | None = None,
    job_status: AutoLabelProgress = AutoLabelProgress.PENDING,
    claim_token: uuid.UUID | None = None,
    claim_expires_offset: timedelta | None = None,
    updated_offset: timedelta | None = None,
    with_items: bool = True,
) -> tuple[uuid.UUID, list[AutoLabel]]:
    run_id = scenario.autolabel_runs["cluener"].run_id
    target_group_id = label_group_id or scenario.label_groups["labels"].label_group_id
    autolabels = list(
        db.scalars(
            select(AutoLabel)
            .where(AutoLabel.run_id == run_id, AutoLabel.auto_label_status == AutoLabelProgress.DONE)
            .order_by(AutoLabel.chapter_content_id)
        )
    )
    claim_expires_at = func.clock_timestamp() + claim_expires_offset if claim_expires_offset is not None else None
    updated_at = func.clock_timestamp() + updated_offset if updated_offset is not None else func.clock_timestamp()
    promotion_id = db.execute(
        insert(LabelPromotionJob)
        .values(
            run_id=run_id,
            label_group_id=target_group_id,
            requested_by=scenario.users["owner"].user_id,
            status=job_status,
            claim_token=claim_token,
            claim_expires_at=claim_expires_at,
            created_at=updated_at,
            updated_at=updated_at,
        )
        .returning(LabelPromotionJob.promotion_id)
    ).scalar_one()
    if with_items:
        db.execute(
            insert(LabelPromotionJobItem),
            [
                {"promotion_id": promotion_id, "auto_label_id": autolabel.auto_label_id, "position": position}
                for position, autolabel in enumerate(autolabels)
            ],
        )
    db.commit()
    return promotion_id, autolabels


def _label_count(db: Session, label_group_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Label)
            .join(LabelData, LabelData.label_data_id == Label.label_data_id)
            .where(LabelData.label_group_id == label_group_id)
        )
        or 0
    )


async def test_failed_initial_enqueue_is_recovered_by_sweep_with_original_job_id(
    client: TestClient,
    test_db: Session,
    async_test_db: AsyncSession,
    xianxia_autolabels_scenario: DatabaseScenario,
    recording_promotion_dispatcher: RecordingPromotionDispatcher,
) -> None:
    scenario = xianxia_autolabels_scenario
    _add_autolabelled_chapters(test_db, scenario)
    test_db.commit()
    owner = scenario.users["owner"]
    label_group_id = scenario.label_groups["labels"].label_group_id
    run_id = scenario.autolabel_runs["cluener"].run_id

    recording_promotion_dispatcher.enqueue_error = EnqueueFailedException("broker unavailable")
    response = client.post(
        f"/label-groups/{label_group_id}/label-promotions",
        json={"runId": str(run_id)},
        headers=_headers(owner),
    )
    assert response.status_code == status.HTTP_202_ACCEPTED
    promotion_id = uuid.UUID(response.json()["promotionId"])
    item_count = response.json()["itemCount"]
    assert item_count >= 4
    assert recording_promotion_dispatcher.promotions == []

    repeat = client.post(
        f"/label-groups/{label_group_id}/label-promotions",
        json={"runId": str(run_id)},
        headers=_headers(owner),
    )
    assert repeat.status_code == status.HTTP_409_CONFLICT

    test_db.execute(
        update(LabelPromotionJob)
        .where(LabelPromotionJob.promotion_id == promotion_id)
        .values(updated_at=func.clock_timestamp() - PENDING_PROMOTION_GRACE_PERIOD - timedelta(seconds=5))
    )
    test_db.commit()

    sweep_dispatcher = RecordingPromotionDispatcher()
    result = await sweep_stale_promotions(async_test_db, sweep_dispatcher)

    assert result == PromotionSweepResult(enqueued=(promotion_id,), failed=())
    assert sweep_dispatcher.promotions == [promotion_id]

    assert await process_promotion_job(async_test_db, sweep_dispatcher.promotions[0])
    assert set(_outcomes(test_db, promotion_id).values()) == {(PromotionItemOutcome.DONE, None)}
    job = test_db.get_one(LabelPromotionJob, promotion_id)
    assert job.status == AutoLabelProgress.DONE
    assert job.claim_token is None and job.claim_expires_at is None
    assert _label_data_count(test_db, label_group_id) == item_count
    expected_labels = sum(
        len(data or [])
        for data in test_db.scalars(
            select(AutoLabel.auto_label_data)
            .join(LabelPromotionJobItem, LabelPromotionJobItem.auto_label_id == AutoLabel.auto_label_id)
            .where(LabelPromotionJobItem.promotion_id == promotion_id)
        )
    )
    assert expected_labels > 0
    assert _label_count(test_db, label_group_id) == expected_labels


async def test_expired_claim_lease_is_redispatched_and_finishes_with_original_job_id(
    test_db: Session, async_test_db: AsyncSession, xianxia_autolabels_scenario: DatabaseScenario
) -> None:
    scenario = xianxia_autolabels_scenario
    _add_autolabelled_chapters(test_db, scenario)
    label_group_id = scenario.label_groups["labels"].label_group_id
    promotion_id, autolabels = _create_promotion_job(
        test_db,
        scenario,
        job_status=AutoLabelProgress.PROCESSING,
        claim_token=uuid.uuid4(),
        claim_expires_offset=-timedelta(seconds=5),
    )

    sweep_dispatcher = RecordingPromotionDispatcher()
    result = await sweep_stale_promotions(async_test_db, sweep_dispatcher)

    assert result == PromotionSweepResult(enqueued=(promotion_id,), failed=())
    assert sweep_dispatcher.promotions == [promotion_id]

    assert await process_promotion_job(async_test_db, sweep_dispatcher.promotions[0])
    assert set(_outcomes(test_db, promotion_id).values()) == {(PromotionItemOutcome.DONE, None)}
    job = test_db.get_one(LabelPromotionJob, promotion_id)
    assert job.status == AutoLabelProgress.DONE
    assert job.claim_token is None and job.claim_expires_at is None
    assert _label_data_count(test_db, label_group_id) == len(autolabels)
    expected_labels = sum(len(autolabel.auto_label_data or []) for autolabel in autolabels)
    assert expected_labels > 0
    assert _label_count(test_db, label_group_id) == expected_labels


async def test_duplicate_delivery_persists_a_single_set_of_labels(
    test_db: Session, async_test_db: AsyncSession, xianxia_autolabels_scenario: DatabaseScenario
) -> None:
    scenario = xianxia_autolabels_scenario
    _add_autolabelled_chapters(test_db, scenario)
    label_group_id = scenario.label_groups["labels"].label_group_id
    promotion_id, autolabels = _create_promotion_job(
        test_db,
        scenario,
        updated_offset=-(PENDING_PROMOTION_GRACE_PERIOD + timedelta(seconds=5)),
    )

    sweep_dispatcher = RecordingPromotionDispatcher()
    await sweep_stale_promotions(async_test_db, sweep_dispatcher)
    await sweep_stale_promotions(async_test_db, sweep_dispatcher)
    assert sweep_dispatcher.promotions == [promotion_id, promotion_id]

    outcomes = [await process_promotion_job(async_test_db, pid) for pid in sweep_dispatcher.promotions]
    assert outcomes == [True, False]

    test_db.expire_all()
    assert test_db.get_one(LabelPromotionJob, promotion_id).status == AutoLabelProgress.DONE
    assert _label_data_count(test_db, label_group_id) == len(autolabels)
    expected_labels = sum(len(autolabel.auto_label_data or []) for autolabel in autolabels)
    assert expected_labels > 0
    assert _label_count(test_db, label_group_id) == expected_labels


async def test_fresh_pending_live_claimed_and_finished_jobs_are_not_redispatched(
    test_db: Session, async_test_db: AsyncSession, xianxia_autolabels_scenario: DatabaseScenario
) -> None:
    scenario = xianxia_autolabels_scenario
    second_group_id = _add_label_group(test_db, scenario, "live-processing-group")

    _create_promotion_job(
        test_db,
        scenario,
        job_status=AutoLabelProgress.PENDING,
        updated_offset=timedelta(seconds=0),
        with_items=False,
    )
    _create_promotion_job(
        test_db,
        scenario,
        label_group_id=second_group_id,
        job_status=AutoLabelProgress.PROCESSING,
        claim_token=uuid.uuid4(),
        claim_expires_offset=timedelta(minutes=2),
        updated_offset=-timedelta(minutes=5),
        with_items=False,
    )
    _create_promotion_job(
        test_db,
        scenario,
        job_status=AutoLabelProgress.DONE,
        updated_offset=-timedelta(hours=1),
        with_items=False,
    )
    _create_promotion_job(
        test_db,
        scenario,
        job_status=AutoLabelProgress.FAILED,
        updated_offset=-timedelta(hours=1),
        with_items=False,
    )

    sweep_dispatcher = RecordingPromotionDispatcher()
    result = await sweep_stale_promotions(async_test_db, sweep_dispatcher)

    assert result == PromotionSweepResult(enqueued=(), failed=())
    assert sweep_dispatcher.promotions == []


async def test_enqueue_error_on_one_stale_job_is_logged_and_does_not_abort_others(
    test_db: Session,
    async_test_db: AsyncSession,
    xianxia_autolabels_scenario: DatabaseScenario,
    caplog: pytest.LogCaptureFixture,
) -> None:
    scenario = xianxia_autolabels_scenario
    second_group_id = _add_label_group(test_db, scenario, "second-stale-group")

    failing_id, _ = _create_promotion_job(
        test_db,
        scenario,
        job_status=AutoLabelProgress.PENDING,
        updated_offset=-timedelta(minutes=5),
        with_items=False,
    )
    succeeding_id, _ = _create_promotion_job(
        test_db,
        scenario,
        label_group_id=second_group_id,
        job_status=AutoLabelProgress.PROCESSING,
        claim_token=uuid.uuid4(),
        claim_expires_offset=-timedelta(minutes=1),
        updated_offset=-timedelta(minutes=1),
        with_items=False,
    )

    class FlakyPromotionDispatcher:
        def __init__(self) -> None:
            self.promotions: list[uuid.UUID] = []

        async def aenqueue(self, promotion_id: uuid.UUID) -> None:
            if promotion_id == failing_id:
                raise EnqueueFailedException("broker timeout")
            self.promotions.append(promotion_id)

    dispatcher = FlakyPromotionDispatcher()
    with caplog.at_level(logging.ERROR, logger="src.autolabels.promotions.sweeper"):
        result = await sweep_stale_promotions(async_test_db, dispatcher)

    assert result == PromotionSweepResult(enqueued=(succeeding_id,), failed=(failing_id,))
    assert dispatcher.promotions == [succeeding_id]
    assert str(failing_id) in caplog.text
