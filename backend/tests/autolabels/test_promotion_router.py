import uuid
from datetime import timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.auth.utils import create_access_token
from src.autolabels.constants import MAX_POLLED_PROMOTIONS, AutoLabelProgress
from src.autolabels.models import AutoLabel, LabelPromotionJobItem
from src.autolabels.promotions.processing import process_promotion_job
from src.labels.models import LabelData
from src.novels.constants import Role, Visibility
from src.novels.models import NovelContributor
from test_support.autolabels import RecordingPromotionDispatcher
from test_support.test_data.scenarios import DatabaseScenario
from tests.autolabels.test_promotion_processing import _add_autolabelled_chapters


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.user_name}, timedelta(minutes=30))}"}


def _promote(client: TestClient, scenario: DatabaseScenario, user: User, **body: object):
    return client.post(
        f"/label-groups/{scenario.label_groups['labels'].label_group_id}/label-promotions",
        json={"runId": str(scenario.autolabel_runs["cluener"].run_id), **body},
        headers=_headers(user),
    )


def _list(client: TestClient, scenario: DatabaseScenario, user: User):
    return client.get(f"/novels/{scenario.novels['novel'].novel_id}/label-promotions", headers=_headers(user))


def test_creating_a_promotion_selects_items_and_enqueues_it(
    client: TestClient,
    test_db: Session,
    xianxia_autolabels_scenario: DatabaseScenario,
    recording_promotion_dispatcher: RecordingPromotionDispatcher,
) -> None:
    scenario = xianxia_autolabels_scenario
    _add_autolabelled_chapters(test_db, scenario)
    test_db.commit()
    owner = scenario.users["owner"]

    response = _promote(client, scenario, owner)

    assert response.status_code == status.HTTP_202_ACCEPTED
    job = response.json()
    assert job["itemCount"] >= 5
    assert recording_promotion_dispatcher.promotions == [uuid.UUID(job["promotionId"])]

    # While the job is active, another one for the same run and group is rejected.
    again = _promote(client, scenario, owner)
    assert again.status_code == status.HTTP_409_CONFLICT
    assert recording_promotion_dispatcher.promotions == [uuid.UUID(job["promotionId"])]


async def test_chapters_with_label_data_are_not_selected_and_an_empty_job_finishes_at_once(
    client: TestClient,
    test_db: Session,
    async_test_db: AsyncSession,
    xianxia_autolabels_scenario: DatabaseScenario,
    recording_promotion_dispatcher: RecordingPromotionDispatcher,
) -> None:
    scenario = xianxia_autolabels_scenario
    group_id = scenario.label_groups["labels"].label_group_id
    for chapter_content_id in test_db.scalars(
        select(AutoLabel.chapter_content_id).where(AutoLabel.run_id == scenario.autolabel_runs["cluener"].run_id)
    ):
        test_db.add(LabelData(label_group_id=group_id, chapter_content_id=chapter_content_id))
    test_db.commit()

    response = _promote(client, scenario, scenario.users["owner"])

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["itemCount"] == 0
    promotion_id = uuid.UUID(response.json()["promotionId"])
    assert recording_promotion_dispatcher.promotions == [promotion_id]
    assert await process_promotion_job(async_test_db, promotion_id)
    assert _list(client, scenario, scenario.users["owner"]).json()[0]["status"] == "done"


def test_missing_groups_and_runs_are_not_found(
    client: TestClient, xianxia_autolabels_scenario: DatabaseScenario
) -> None:
    scenario = xianxia_autolabels_scenario
    owner = scenario.users["owner"]

    missing_group = client.post(
        f"/label-groups/{uuid.uuid4()}/label-promotions",
        json={"runId": str(scenario.autolabel_runs["cluener"].run_id)},
        headers=_headers(owner),
    )
    missing_run = _promote(client, scenario, owner, runId=str(uuid.uuid4()))

    assert missing_group.status_code == status.HTTP_404_NOT_FOUND
    assert missing_run.status_code == status.HTTP_404_NOT_FOUND


async def test_listing_reports_progress_counts_and_failures(
    client: TestClient,
    test_db: Session,
    async_test_db: AsyncSession,
    xianxia_autolabels_scenario: DatabaseScenario,
) -> None:
    scenario = xianxia_autolabels_scenario
    _add_autolabelled_chapters(test_db, scenario)
    test_db.commit()
    owner = scenario.users["owner"]
    created = _promote(client, scenario, owner).json()
    promotion_id = uuid.UUID(created["promotionId"])

    listed = _list(client, scenario, owner)
    assert listed.status_code == status.HTTP_200_OK
    assert [job["promotionId"] for job in listed.json()] == [created["promotionId"]]
    assert listed.json()[0]["status"] == "pending"
    assert listed.json()[0]["counts"]["pending"] == created["itemCount"]

    # Break one item's text so it fails, then run the job.
    first_item = test_db.scalar(
        select(AutoLabel)
        .join(LabelPromotionJobItem, LabelPromotionJobItem.auto_label_id == AutoLabel.auto_label_id)
        .where(LabelPromotionJobItem.promotion_id == promotion_id)
        .order_by(LabelPromotionJobItem.position)
        .limit(1)
    )
    assert first_item is not None and first_item.auto_label_data
    broken = [dict(label) for label in first_item.auto_label_data]
    broken[0]["label_word"] = "not in the text"
    test_db.execute(
        update(AutoLabel).where(AutoLabel.auto_label_id == first_item.auto_label_id).values(auto_label_data=broken)
    )
    test_db.commit()
    assert await process_promotion_job(async_test_db, promotion_id)

    finished = _list(client, scenario, owner).json()[0]
    assert finished["status"] == "done"
    assert finished["counts"] == {
        "total": created["itemCount"],
        "done": created["itemCount"] - 1,
        "failed": 1,
        "pending": 0,
    }
    failures = client.get(f"/label-promotions/{promotion_id}/failures", headers=_headers(owner))
    assert failures.status_code == status.HTTP_200_OK
    assert [failure["message"] for failure in failures.json()] == ["Text mismatch between autolabel and chapter."]
    assert failures.json()[0]["chapterNum"] is not None
    outsider = User(user_name="outsider", user_hashed_password="unused", user_type=UserType.USER)
    test_db.add(outsider)
    test_db.commit()
    public_failures = client.get(f"/label-promotions/{promotion_id}/failures", headers=_headers(outsider))
    assert len(public_failures.json()) == 1
    scenario.novels["novel"].novel_visibility = Visibility.PRIVATE
    test_db.commit()
    hidden = client.get(f"/label-promotions/{promotion_id}/failures", headers=_headers(outsider))
    assert hidden.json() == []


def test_listing_by_promotion_ids_returns_only_those_jobs(
    client: TestClient, test_db: Session, xianxia_autolabels_scenario: DatabaseScenario
) -> None:
    scenario = xianxia_autolabels_scenario
    _add_autolabelled_chapters(test_db, scenario)
    test_db.commit()
    owner = scenario.users["owner"]
    promotion_id = _promote(client, scenario, owner).json()["promotionId"]
    url = f"/novels/{scenario.novels['novel'].novel_id}/label-promotions"

    tracked = client.get(
        url, params={"promotionIds": [promotion_id, str(uuid.uuid4())], "limit": 1}, headers=_headers(owner)
    )
    other_novel = client.get(
        f"/novels/{uuid.uuid4()}/label-promotions", params={"promotionIds": [promotion_id]}, headers=_headers(owner)
    )
    too_many = client.get(
        url,
        params={"promotionIds": [str(uuid.uuid4()) for _ in range(MAX_POLLED_PROMOTIONS + 1)]},
        headers=_headers(owner),
    )

    assert tracked.status_code == status.HTTP_200_OK
    assert [job["promotionId"] for job in tracked.json()] == [promotion_id]
    assert other_novel.json() == []
    assert too_many.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_novel_viewers_cannot_promote(
    client: TestClient,
    test_db: Session,
    xianxia_autolabels_scenario: DatabaseScenario,
    recording_promotion_dispatcher: RecordingPromotionDispatcher,
) -> None:
    scenario = xianxia_autolabels_scenario
    owner = scenario.users["owner"]
    contributor = test_db.execute(
        select(NovelContributor).where(
            NovelContributor.novel_id == scenario.novels["novel"].novel_id,
            NovelContributor.user_id == owner.user_id,
        )
    ).scalar_one()
    contributor.contributor_role = Role.VIEWER
    test_db.commit()

    response = _promote(client, scenario, owner)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert recording_promotion_dispatcher.promotions == []


def test_promotion_ignores_autolabels_from_other_novels_in_the_run(
    client: TestClient,
    test_db: Session,
    xianxia_autolabels_scenario: DatabaseScenario,
    scifi_scenario: DatabaseScenario,
) -> None:
    scenario = xianxia_autolabels_scenario
    foreign_content = scifi_scenario.contents["novel:xianxia-translation-chapter-0001-v0001"]
    foreign = AutoLabel(
        auto_label_data=[],
        auto_label_status=AutoLabelProgress.DONE,
        chapter_content_id=foreign_content.chapter_content_id,
        run_id=scenario.autolabel_runs["cluener"].run_id,
    )
    test_db.add(foreign)
    test_db.commit()

    response = _promote(client, scenario, scenario.users["owner"])

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["itemCount"] == len(scenario.autolabels)
    item_ids = test_db.scalars(
        select(LabelPromotionJobItem.auto_label_id).where(
            LabelPromotionJobItem.promotion_id == uuid.UUID(response.json()["promotionId"])
        )
    ).all()
    assert foreign.auto_label_id not in item_ids
