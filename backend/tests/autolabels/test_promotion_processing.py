import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.autolabels.constants import AutoLabelProgress, PromotionItemOutcome
from src.autolabels.models import AutoLabel, LabelPromotionJob, LabelPromotionJobItem
from src.autolabels.promotions import processing
from src.autolabels.promotions.processing import PromotionClaimLostError, process_promotion_job
from src.labels.models import Label, LabelData
from src.novels.models import Chapter, ChapterContent
from test_support.test_data.scenarios import DatabaseScenario

EXTRA_CHAPTER_TEXTS = ["青云山下有座小镇。", "少年背着剑走进城门。", "长老在大殿里等候多时。", "雨夜里传来一阵钟声。"]


def _add_autolabelled_chapters(db: Session, scenario: DatabaseScenario) -> None:
    run_id = scenario.autolabel_runs["cluener"].run_id
    novel_id = scenario.novels["novel"].novel_id
    for index, text in enumerate(EXTRA_CHAPTER_TEXTS):
        chapter = Chapter(novel_id=novel_id, chapter_num=1000 + index, chapter_title="extra", chapter_is_public=False)
        db.add(chapter)
        db.flush()
        content = ChapterContent(chapter_id=chapter.chapter_id, chapter_content_text=text, chapter_content_version=1)
        db.add(content)
        db.flush()
        labels = [
            {"label_start": start, "label_end": end, "label_word": text[start:end], "label_entity_group": "name"}
            for start, end in ((0, 2), (4, 6))
        ]
        db.add(
            AutoLabel(
                run_id=run_id,
                chapter_content_id=content.chapter_content_id,
                auto_label_status=AutoLabelProgress.DONE,
                auto_label_data=labels,
            )
        )
    db.flush()


def _create_job(
    db: Session,
    scenario: DatabaseScenario,
    *,
    claim_token: uuid.UUID | None = None,
    claim_expires_at: datetime | None = None,
) -> tuple[uuid.UUID, list[AutoLabel]]:
    _add_autolabelled_chapters(db, scenario)
    run_id = scenario.autolabel_runs["cluener"].run_id
    autolabels = list(
        db.scalars(
            select(AutoLabel)
            .where(AutoLabel.run_id == run_id, AutoLabel.auto_label_status == AutoLabelProgress.DONE)
            .order_by(AutoLabel.chapter_content_id)
        )
    )
    assert len(autolabels) >= 3
    promotion_id = db.execute(
        insert(LabelPromotionJob)
        .values(
            run_id=run_id,
            label_group_id=scenario.label_groups["labels"].label_group_id,
            requested_by=scenario.users["owner"].user_id,
            status=AutoLabelProgress.PENDING if claim_token is None else AutoLabelProgress.PROCESSING,
            claim_token=claim_token,
            claim_expires_at=claim_expires_at,
        )
        .returning(LabelPromotionJob.promotion_id)
    ).scalar_one()
    db.execute(
        insert(LabelPromotionJobItem),
        [
            {"promotion_id": promotion_id, "auto_label_id": autolabel.auto_label_id, "position": position}
            for position, autolabel in enumerate(autolabels)
        ],
    )
    db.commit()
    return promotion_id, autolabels


def _outcomes(db: Session, promotion_id: uuid.UUID) -> dict[uuid.UUID, tuple[str | None, str | None]]:
    db.expire_all()
    rows = db.execute(
        select(LabelPromotionJobItem.auto_label_id, LabelPromotionJobItem.outcome, LabelPromotionJobItem.message).where(
            LabelPromotionJobItem.promotion_id == promotion_id
        )
    )
    return {auto_label_id: (outcome, message) for auto_label_id, outcome, message in rows}


def _label_data_count(db: Session, label_group_id: uuid.UUID, chapter_content_id: uuid.UUID | None = None) -> int:
    query = select(func.count()).select_from(LabelData).where(LabelData.label_group_id == label_group_id)
    if chapter_content_id is not None:
        query = query.where(LabelData.chapter_content_id == chapter_content_id)
    return db.scalar(query) or 0


async def test_processes_every_item_and_finishes_the_job(
    test_db: Session, async_test_db: AsyncSession, xianxia_autolabels_scenario: DatabaseScenario
) -> None:
    promotion_id, autolabels = _create_job(test_db, xianxia_autolabels_scenario)
    label_group_id = xianxia_autolabels_scenario.label_groups["labels"].label_group_id

    assert await process_promotion_job(async_test_db, promotion_id, batch_size=2)

    assert set(_outcomes(test_db, promotion_id).values()) == {(PromotionItemOutcome.DONE, None)}
    job = test_db.get_one(LabelPromotionJob, promotion_id)
    assert job.status == AutoLabelProgress.DONE
    assert job.claim_token is None and job.claim_expires_at is None
    assert _label_data_count(test_db, label_group_id) == len(autolabels)
    labels = test_db.scalar(
        select(func.count())
        .select_from(Label)
        .join(LabelData, LabelData.label_data_id == Label.label_data_id)
        .where(LabelData.label_group_id == label_group_id)
    )
    assert labels == sum(len(autolabel.auto_label_data or []) for autolabel in autolabels)


async def test_items_that_cannot_be_promoted_fail_without_stopping_the_rest(
    test_db: Session, async_test_db: AsyncSession, xianxia_autolabels_scenario: DatabaseScenario
) -> None:
    promotion_id, autolabels = _create_job(test_db, xianxia_autolabels_scenario)
    label_group_id = xianxia_autolabels_scenario.label_groups["labels"].label_group_id
    changed, mismatched, already_labelled = autolabels[0], autolabels[1], autolabels[2]

    content = test_db.get_one(ChapterContent, changed.chapter_content_id)
    test_db.add(
        ChapterContent(
            chapter_id=content.chapter_id,
            chapter_content_text=content.chapter_content_text + "!",
            chapter_content_version=content.chapter_content_version + 1,
        )
    )
    bad_labels = [dict(label) for label in mismatched.auto_label_data or []]
    assert bad_labels
    bad_labels[0]["label_word"] = "not in the text"
    test_db.execute(
        update(AutoLabel).where(AutoLabel.auto_label_id == mismatched.auto_label_id).values(auto_label_data=bad_labels)
    )
    test_db.add(LabelData(label_group_id=label_group_id, chapter_content_id=already_labelled.chapter_content_id))
    test_db.commit()

    assert await process_promotion_job(async_test_db, promotion_id)

    outcomes = _outcomes(test_db, promotion_id)
    assert outcomes.pop(changed.auto_label_id) == (
        PromotionItemOutcome.FAILED,
        "The chapter changed after the promotion was requested.",
    )
    assert outcomes.pop(mismatched.auto_label_id) == (
        PromotionItemOutcome.FAILED,
        "Text mismatch between autolabel and chapter.",
    )
    assert outcomes.pop(already_labelled.auto_label_id) == (
        PromotionItemOutcome.FAILED,
        "The chapter already has label data in this label group.",
    )
    assert set(outcomes.values()) <= {(PromotionItemOutcome.DONE, None)}
    assert _label_data_count(test_db, label_group_id, changed.chapter_content_id) == 0
    assert _label_data_count(test_db, label_group_id, mismatched.chapter_content_id) == 0
    assert test_db.get_one(LabelPromotionJob, promotion_id).status == AutoLabelProgress.DONE


async def test_resumes_from_unprocessed_items(
    test_db: Session, async_test_db: AsyncSession, xianxia_autolabels_scenario: DatabaseScenario
) -> None:
    promotion_id, autolabels = _create_job(test_db, xianxia_autolabels_scenario)
    label_group_id = xianxia_autolabels_scenario.label_groups["labels"].label_group_id
    test_db.execute(
        update(LabelPromotionJobItem)
        .where(
            LabelPromotionJobItem.promotion_id == promotion_id,
            LabelPromotionJobItem.auto_label_id == autolabels[0].auto_label_id,
        )
        .values(outcome=PromotionItemOutcome.DONE)
    )
    test_db.commit()

    assert await process_promotion_job(async_test_db, promotion_id)

    assert _label_data_count(test_db, label_group_id, autolabels[0].chapter_content_id) == 0
    assert _label_data_count(test_db, label_group_id) == len(autolabels) - 1


async def test_live_claims_block_and_expired_claims_are_reclaimed(
    test_db: Session, async_test_db: AsyncSession, xianxia_autolabels_scenario: DatabaseScenario
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    live, _ = _create_job(
        test_db,
        xianxia_autolabels_scenario,
        claim_token=uuid.uuid4(),
        claim_expires_at=now + timedelta(hours=1),
    )

    assert not await process_promotion_job(async_test_db, live)
    assert set(_outcomes(test_db, live).values()) == {(None, None)}

    test_db.execute(
        update(LabelPromotionJob)
        .where(LabelPromotionJob.promotion_id == live)
        .values(claim_expires_at=now - timedelta(hours=1))
    )
    test_db.commit()

    assert await process_promotion_job(async_test_db, live)
    assert test_db.get_one(LabelPromotionJob, live).status == AutoLabelProgress.DONE


async def test_a_lost_claim_stops_the_worker_and_keeps_committed_batches(
    test_db: Session,
    async_test_db: AsyncSession,
    xianxia_autolabels_scenario: DatabaseScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotion_id, _ = _create_job(test_db, xianxia_autolabels_scenario)
    other_token = uuid.uuid4()
    check_items = processing._check_items
    calls = 0

    async def take_over_after_first_batch(db: AsyncSession, auto_label_ids: list[uuid.UUID]):
        nonlocal calls
        calls += 1
        if calls == 2:
            test_db.execute(
                update(LabelPromotionJob)
                .where(LabelPromotionJob.promotion_id == promotion_id)
                .values(claim_token=other_token)
            )
            test_db.commit()
        return await check_items(db, auto_label_ids)

    monkeypatch.setattr(processing, "_check_items", take_over_after_first_batch)

    with pytest.raises(PromotionClaimLostError):
        await process_promotion_job(async_test_db, promotion_id, batch_size=1)

    outcomes = _outcomes(test_db, promotion_id)
    assert sum(outcome == PromotionItemOutcome.DONE for outcome, _ in outcomes.values()) == 1
    job = test_db.get_one(LabelPromotionJob, promotion_id)
    assert job.status == AutoLabelProgress.PROCESSING
    assert job.claim_token == other_token


TEXT = "青云山下有座小镇。"


@pytest.mark.parametrize(
    ("labels", "problem"),
    [
        ([{"label_word": "青云", "label_start": 0, "label_end": 2}], None),
        ([], None),
        ({"label_word": "青云"}, "The autolabel data is not a list of labels."),
        ([{"label_start": 0, "label_end": 2}], "A label is missing its word, start or end."),
        ([{"label_word": "青云", "label_start": True, "label_end": 2}], "A label is missing its word, start or end."),
        (
            [{"label_word": "", "label_start": 2, "label_end": 2}],
            "A label's span is empty or outside the chapter text.",
        ),
        (
            [{"label_word": "镇。", "label_start": 7, "label_end": 99}],
            "A label's span is empty or outside the chapter text.",
        ),
        (
            [{"label_word": "青云", "label_start": 0, "label_end": 2, "label_entity_group": "x" * 65}],
            "A label's entity group is not text of at most 64 characters.",
        ),
        (
            [{"label_word": "青云", "label_start": 0, "label_end": 2, "label_score": 1.5}],
            "A label's score is not a number between 0 and 1.",
        ),
        (
            [{"label_word": "青云", "label_start": 0, "label_end": 2, "label_dirty": "yes"}],
            "A label's dirty flag is not a boolean.",
        ),
        ([{"label_word": "小镇", "label_start": 0, "label_end": 2}], "Text mismatch between autolabel and chapter."),
        (
            [
                {"label_word": "青云", "label_start": 0, "label_end": 2},
                {"label_word": "云山", "label_start": 1, "label_end": 3},
            ],
            "Labels in the autolabel data overlap.",
        ),
    ],
)
def test_label_problems_cover_what_the_labels_table_rejects(labels: object, problem: str | None) -> None:
    assert processing._label_problem(TEXT, labels) == problem


def test_label_words_longer_than_the_column_are_rejected() -> None:
    text = "字" * 200
    labels = [{"label_word": text[:129], "label_start": 0, "label_end": 129}]
    assert processing._label_problem(text, labels) == "A label's word is longer than 128 characters."
