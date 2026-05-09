"""Router tests for the editing aggregate endpoint."""

import uuid
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from tests.fixtures.bundles import ScenarioBundle
from tests.gate_logging import log_gate

pytestmark = pytest.mark.dependency(
    depends=["gate::fixture_validation", "gate::labels::permissions", "gate::novels::permissions"],
    scope="session",
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _editing_url(chapter_id: uuid.UUID) -> str:
    return f"/edit-chapter-data/{chapter_id}"


def _versioned_user(bundle: ScenarioBundle, user_name: str) -> User:
    return bundle.users.by_name[user_name]


def _normalize_payload(payload: dict[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    label_group_list = cast(list[dict[str, Any]], normalized["labelGroupList"])
    label_data_list = cast(list[dict[str, Any]], normalized["labelDataList"])
    normalized["labelGroupList"] = sorted(
        label_group_list,
        key=lambda entry: entry["labelGroup"]["labelGroupName"],
    )
    normalized["labelDataList"] = sorted(
        [
            {
                **entry,
                "labels": sorted(
                    entry["labels"],
                    key=lambda label: (label["labelStart"], label["labelEnd"], label["labelWord"]),
                ),
            }
            for entry in label_data_list
        ],
        key=lambda entry: entry["labelDataId"],
    )
    return normalized


class TestReadEditChapterData:
    @pytest.mark.dependency(name="editing::router::owner_happy_path", scope="session")
    def test_owner_happy_path(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        actor = _versioned_user(versioned_chapter_scenario, "to_user")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        novel_bundle = versioned_chapter_scenario.novels[0]

        response = client.get(
            _editing_url(chapter_bundle.chapter.chapter_id),
            params={
                "novelId": str(novel_bundle.novel.novel_id),
                "labelGroupsNum": 2,
            },
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()

        assert payload["chapter"]["chapterId"] == str(chapter_bundle.chapter.chapter_id)
        assert payload["chapter"]["novelId"] == str(novel_bundle.novel.novel_id)
        assert payload["chapterContent"]["chapterContentId"] == str(chapter_bundle.latest_content.chapter_content_id)
        assert payload["role"] == "owner"

        assert {entry["labelGroup"]["labelGroupName"] for entry in payload["labelGroupList"]} == {"Group 1", "Group 2"}

        label_data_ids_from_groups = {
            entry["labelData"]["labelDataId"] for entry in payload["labelGroupList"] if entry["labelData"] is not None
        }
        assert len(payload["labelDataList"]) == 2
        assert {entry["labelDataId"] for entry in payload["labelDataList"]} == label_data_ids_from_groups

    @pytest.mark.dependency(name="editing::router::admin_subject_override", scope="session")
    def test_admin_subject_override(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        owner = _versioned_user(versioned_chapter_scenario, "to_user")
        admin = _versioned_user(versioned_chapter_scenario, "to_admin")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        novel_bundle = versioned_chapter_scenario.novels[0]

        owner_response = client.get(
            _editing_url(chapter_bundle.chapter.chapter_id),
            params={
                "novelId": str(novel_bundle.novel.novel_id),
                "labelGroupsNum": 2,
            },
            headers=_auth_headers(owner),
        )
        admin_response = client.get(
            _editing_url(chapter_bundle.chapter.chapter_id),
            params={
                "novelId": str(novel_bundle.novel.novel_id),
                "labelGroupsNum": 2,
                "subjectId": str(owner.user_id),
            },
            headers=_auth_headers(admin),
        )

        assert owner_response.status_code == status.HTTP_200_OK
        assert admin_response.status_code == status.HTTP_200_OK
        assert _normalize_payload(admin_response.json()) == _normalize_payload(owner_response.json())

    @pytest.mark.dependency(name="editing::router::non_admin_subject_forbidden", scope="session")
    def test_non_admin_subject_forbidden(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        owner = _versioned_user(versioned_chapter_scenario, "to_user")
        other_user = _versioned_user(versioned_chapter_scenario, "to_other")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        novel_bundle = versioned_chapter_scenario.novels[0]

        response = client.get(
            _editing_url(chapter_bundle.chapter.chapter_id),
            params={
                "novelId": str(novel_bundle.novel.novel_id),
                "labelGroupsNum": 2,
                "subjectId": str(owner.user_id),
            },
            headers=_auth_headers(other_user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.dependency(name="editing::router::admin_subject_not_found", scope="session")
    def test_admin_subject_not_found(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        admin = _versioned_user(versioned_chapter_scenario, "to_admin")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        novel_bundle = versioned_chapter_scenario.novels[0]

        response = client.get(
            _editing_url(chapter_bundle.chapter.chapter_id),
            params={
                "novelId": str(novel_bundle.novel.novel_id),
                "labelGroupsNum": 2,
                "subjectId": str(uuid.uuid4()),
            },
            headers=_auth_headers(admin),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.dependency(name="editing::router::cap_consistency", scope="session")
    def test_label_groups_num_caps_loaded_label_datas_consistently(
        self,
        client: TestClient,
        test_db: Session,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        actor = _versioned_user(versioned_chapter_scenario, "to_user")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        novel_bundle = versioned_chapter_scenario.novels[0]
        existing_label_data_1 = versioned_chapter_scenario.label_groups_by_name["Group 1"].label_data
        existing_label_data_2 = versioned_chapter_scenario.label_groups_by_name["Group 2"].label_data

        extra_group_with_data = LabelGroup(
            label_group_name="Group 3",
            novel_id=novel_bundle.novel.novel_id,
        )
        extra_group_without_data = LabelGroup(
            label_group_name="Group 4",
            novel_id=novel_bundle.novel.novel_id,
        )
        test_db.add_all([extra_group_with_data, extra_group_without_data])
        test_db.commit()

        extra_contributors = [
            LabelContributor(
                label_group_id=extra_group_with_data.label_group_id,
                user_id=actor.user_id,
                label_contributor_role=LabelRole.OWNER,
            ),
            LabelContributor(
                label_group_id=extra_group_without_data.label_group_id,
                user_id=actor.user_id,
                label_contributor_role=LabelRole.OWNER,
            ),
        ]
        test_db.add_all(extra_contributors)
        test_db.commit()

        extra_label_data = LabelData(
            label_group_id=extra_group_with_data.label_group_id,
            chapter_content_id=chapter_bundle.latest_content.chapter_content_id,
        )
        test_db.add(extra_label_data)
        test_db.commit()

        extra_label = Label(
            label_data_id=extra_label_data.label_data_id,
            label_word="This",
            label_start=13,
            label_end=17,
            label_entity_group="MISC",
            label_score=0.8,
            label_dirty=False,
        )
        test_db.add(extra_label)
        test_db.commit()

        existing_label_data_1.updated_at = datetime(2026, 1, 1, 10, 0, 0)
        existing_label_data_2.updated_at = datetime(2026, 1, 1, 9, 0, 0)
        extra_label_data.updated_at = datetime(2026, 1, 1, 11, 0, 0)
        test_db.commit()

        response = client.get(
            _editing_url(chapter_bundle.chapter.chapter_id),
            params={
                "novelId": str(novel_bundle.novel.novel_id),
                "labelGroupsNum": 2,
            },
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()

        assert {entry["labelGroup"]["labelGroupName"] for entry in payload["labelGroupList"]} == {
            "Group 1",
            "Group 2",
            "Group 3",
            "Group 4",
        }

        group_entries_by_name = {entry["labelGroup"]["labelGroupName"]: entry for entry in payload["labelGroupList"]}
        assert group_entries_by_name["Group 4"]["labelData"] is None

        returned_label_data_ids = {entry["labelDataId"] for entry in payload["labelDataList"]}
        expected_label_data_ids = {
            str(extra_label_data.label_data_id),
            str(existing_label_data_1.label_data_id),
        }
        assert returned_label_data_ids == expected_label_data_ids
        assert str(existing_label_data_2.label_data_id) not in returned_label_data_ids

    @pytest.mark.dependency(
        name="gate::editing::router::read_edit_chapter_data",
        depends=[
            "editing::router::owner_happy_path",
            "editing::router::admin_subject_override",
            "editing::router::non_admin_subject_forbidden",
            "editing::router::admin_subject_not_found",
            "editing::router::cap_consistency",
        ],
        scope="session",
    )
    def test_class_gate(self) -> None:
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::editing::router",
    depends=[
        "gate::editing::router::read_edit_chapter_data",
    ],
    scope="session",
)
def test_gate() -> None:
    """All editing router tests must pass before downstream layers run."""
    log_gate("gate::editing::router")
