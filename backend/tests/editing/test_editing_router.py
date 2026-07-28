"""Router tests for the editing aggregate endpoint."""

import uuid
from datetime import timedelta
from typing import Any, cast

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from test_support.test_data.scenarios import DatabaseScenario


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _editing_url(chapter_id: uuid.UUID) -> str:
    return f"/edit-chapter-data/{chapter_id}"


def _editing_user(bundle: DatabaseScenario, user_name: str) -> User:
    return bundle.users[user_name]


def _eager_params(bundle: DatabaseScenario, *names: str) -> list[str]:
    """Build eager query param values from label group names in the scenario."""
    return [
        str(bundle.label_groups[{"Group 1": "group_1", "Group 2": "group_2"}[name]].label_group_id) for name in names
    ]


def _normalize_payload(payload: dict[str, object]) -> dict[str, object]:
    """Sort entries so two responses can be compared ignoring order."""
    normalized = dict(payload)
    for key in ("noLabelData",):
        normalized[key] = sorted(
            cast(list[dict[str, Any]], normalized[key]),
            key=lambda entry: entry["labelGroupName"],
        )
    for key in ("lazyLabelData",):
        normalized[key] = sorted(
            cast(list[dict[str, Any]], normalized[key]),
            key=lambda entry: entry["labelGroup"]["labelGroupName"],
        )
    for key in ("eagerLabelData",):
        normalized[key] = sorted(
            [
                {
                    **entry,
                    "labels": sorted(
                        cast(list[dict[str, Any]], entry["labels"]),
                        key=lambda lbl: (lbl["labelStart"], lbl["labelEnd"], lbl["labelWord"]),
                    ),
                }
                for entry in cast(list[dict[str, Any]], normalized[key])
            ],
            key=lambda entry: entry["labelGroup"]["labelGroupName"],
        )
    return normalized


class TestReadEditChapterData:
    def test_owner_happy_path(
        self,
        client: TestClient,
        editing_scenario: DatabaseScenario,
    ) -> None:
        actor = _editing_user(editing_scenario, "owner")
        chapter = editing_scenario.chapters["chapter"]
        content = editing_scenario.contents["content_v1"]

        response = client.post(
            _editing_url(chapter.chapter_id),
            json=_eager_params(editing_scenario, "Group 1", "Group 2"),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()

        assert payload["chapterContent"]["chapterContentId"] == str(content.chapter_content_id)

        assert {e["labelGroup"]["labelGroupName"] for e in payload["eagerLabelData"]} == {"Group 1", "Group 2"}
        for entry in payload["eagerLabelData"]:
            assert len(entry["labels"]) > 0

        assert payload["lazyLabelData"] == []
        assert payload["noLabelData"] == []

    def test_admin_subject_override(
        self,
        client: TestClient,
        editing_scenario: DatabaseScenario,
    ) -> None:
        owner = _editing_user(editing_scenario, "owner")
        admin = _editing_user(editing_scenario, "admin")
        chapter = editing_scenario.chapters["chapter"]
        editing_scenario.contents["content_v1"]

        eager = _eager_params(editing_scenario, "Group 1", "Group 2")
        owner_response = client.post(
            _editing_url(chapter.chapter_id),
            json=eager,
            headers=_auth_headers(owner),
        )
        admin_response = client.post(
            _editing_url(chapter.chapter_id),
            json=eager,
            params={"subjectId": str(owner.user_id)},
            headers=_auth_headers(admin),
        )

        assert owner_response.status_code == status.HTTP_200_OK
        assert admin_response.status_code == status.HTTP_200_OK
        assert _normalize_payload(admin_response.json()) == _normalize_payload(owner_response.json())

    def test_non_admin_subject_forbidden(
        self,
        client: TestClient,
        editing_scenario: DatabaseScenario,
    ) -> None:
        owner = _editing_user(editing_scenario, "owner")
        other_user = _editing_user(editing_scenario, "other")
        chapter = editing_scenario.chapters["chapter"]
        editing_scenario.contents["content_v1"]

        response = client.post(
            _editing_url(chapter.chapter_id),
            json=_eager_params(editing_scenario, "Group 1", "Group 2"),
            params={"subjectId": str(owner.user_id)},
            headers=_auth_headers(other_user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_subject_not_found(
        self,
        client: TestClient,
        editing_scenario: DatabaseScenario,
    ) -> None:
        admin = _editing_user(editing_scenario, "admin")
        chapter = editing_scenario.chapters["chapter"]
        editing_scenario.contents["content_v1"]

        response = client.post(
            _editing_url(chapter.chapter_id),
            json=_eager_params(editing_scenario, "Group 1", "Group 2"),
            params={"subjectId": str(uuid.uuid4())},
            headers=_auth_headers(admin),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_eager_lazy_no_split(
        self,
        client: TestClient,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ) -> None:
        actor = _editing_user(editing_scenario, "owner")
        chapter = editing_scenario.chapters["chapter"]
        content = editing_scenario.contents["content_v1"]
        novel = editing_scenario.novels["novel"]

        extra_group_with_data = LabelGroup(
            label_group_name="Group 3",
            novel_id=novel.novel_id,
        )
        extra_group_without_data = LabelGroup(
            label_group_name="Group 4",
            novel_id=novel.novel_id,
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
            chapter_content_id=content.chapter_content_id,
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

        # Eager: only Group 1 and Group 3
        response = client.post(
            _editing_url(chapter.chapter_id),
            json=[
                str(editing_scenario.label_groups["group_1"].label_group_id),
                str(extra_group_with_data.label_group_id),
            ],
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()

        # noLabelData: groups without any LabelData row
        assert {g["labelGroupName"] for g in payload["noLabelData"]} == {"Group 4"}

        # lazyLabelData: groups with LabelData but not in eager
        assert {e["labelGroup"]["labelGroupName"] for e in payload["lazyLabelData"]} == {"Group 2"}

        # eagerLabelData: groups in eager with full labels
        eager_names = {e["labelGroup"]["labelGroupName"] for e in payload["eagerLabelData"]}
        assert eager_names == {"Group 1", "Group 3"}
        for entry in payload["eagerLabelData"]:
            assert len(entry["labels"]) > 0


def _reload_url(chapter_id: uuid.UUID) -> str:
    return f"/edit-chapter-data/{chapter_id}/label-data"


def _reload_params(*label_group_ids: uuid.UUID) -> list[str]:
    return [str(gid) for gid in label_group_ids]


class TestReadEditChapterLabelData:
    """Tests for the reload-group endpoint that fetches / lazily creates LabelData."""

    def test_reload_existing(
        self,
        client: TestClient,
        editing_scenario: DatabaseScenario,
    ) -> None:
        """Reloading a group that already has LabelData returns its labels."""
        actor = _editing_user(editing_scenario, "owner")
        chapter = editing_scenario.chapters["chapter"]
        editing_scenario.contents["content_v1"]
        label_group = editing_scenario.label_groups["group_1"]
        editing_scenario.label_datas["group_1_data"]

        response = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        entry = data[0]
        assert entry["labelGroup"]["labelGroupName"] == "Group 1"
        assert entry["labelData"]["labelGroupId"] == str(label_group.label_group_id)
        assert len(entry["labels"]) == 3

    def test_reload_auto_create(
        self,
        client: TestClient,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ) -> None:
        """Reloading a group without LabelData auto-creates it for editors."""
        actor = _editing_user(editing_scenario, "owner")
        chapter = editing_scenario.chapters["chapter"]
        content = editing_scenario.contents["content_v1"]
        novel = editing_scenario.novels["novel"]

        new_group = LabelGroup(label_group_name="ReloadAutoCreate", novel_id=novel.novel_id)
        test_db.add(new_group)
        test_db.commit()
        test_db.add(
            LabelContributor(
                label_group_id=new_group.label_group_id,
                user_id=actor.user_id,
                label_contributor_role=LabelRole.OWNER,
            )
        )
        test_db.commit()

        # Verify no LabelData exists yet
        assert (
            test_db.query(LabelData)
            .filter(
                LabelData.label_group_id == new_group.label_group_id,
                LabelData.chapter_content_id == content.chapter_content_id,
            )
            .first()
            is None
        )

        response = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(new_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        entry = data[0]
        assert entry["labelGroup"]["labelGroupName"] == "ReloadAutoCreate"
        assert entry["labels"] == []

        # Verify LabelData was created in DB
        ld = (
            test_db.query(LabelData)
            .filter(
                LabelData.label_group_id == new_group.label_group_id,
                LabelData.chapter_content_id == content.chapter_content_id,
            )
            .first()
        )
        assert ld is not None
        assert str(ld.label_data_id) == entry["labelData"]["labelDataId"]

    def test_reload_viewer_no_auto_create(
        self,
        client: TestClient,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ) -> None:
        """A viewer should not trigger auto-create — the group is silently excluded."""
        actor = _editing_user(editing_scenario, "owner")
        viewer = _editing_user(editing_scenario, "other")
        chapter = editing_scenario.chapters["chapter"]
        content = editing_scenario.contents["content_v1"]
        novel = editing_scenario.novels["novel"]

        new_group = LabelGroup(label_group_name="ViewerNoCreate", novel_id=novel.novel_id)
        test_db.add(new_group)
        test_db.commit()
        # Owner creates the group so it exists, then add viewer
        test_db.add(
            LabelContributor(
                label_group_id=new_group.label_group_id,
                user_id=actor.user_id,
                label_contributor_role=LabelRole.OWNER,
            )
        )
        test_db.add(
            LabelContributor(
                label_group_id=new_group.label_group_id,
                user_id=viewer.user_id,
                label_contributor_role=LabelRole.VIEWER,
            )
        )
        test_db.commit()

        response = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(new_group.label_group_id),
            headers=_auth_headers(viewer),
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Viewer should not trigger auto-create — silently excluded
        assert data == []

        # LabelData should NOT exist
        assert (
            test_db.query(LabelData)
            .filter(
                LabelData.label_group_id == new_group.label_group_id,
                LabelData.chapter_content_id == content.chapter_content_id,
            )
            .first()
            is None
        )

    def test_reload_mixed(
        self,
        client: TestClient,
        test_db: Session,
        editing_scenario: DatabaseScenario,
    ) -> None:
        """Mix of groups with existing LabelData and one needing auto-create."""
        actor = _editing_user(editing_scenario, "owner")
        chapter = editing_scenario.chapters["chapter"]
        editing_scenario.contents["content_v1"]
        novel = editing_scenario.novels["novel"]
        label_group = editing_scenario.label_groups["group_1"]
        editing_scenario.label_datas["group_1_data"]

        new_group = LabelGroup(label_group_name="MixedAutoCreate", novel_id=novel.novel_id)
        test_db.add(new_group)
        test_db.commit()
        test_db.add(
            LabelContributor(
                label_group_id=new_group.label_group_id,
                user_id=actor.user_id,
                label_contributor_role=LabelRole.OWNER,
            )
        )
        test_db.commit()

        response = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(label_group.label_group_id, new_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

        names = {e["labelGroup"]["labelGroupName"] for e in data}
        assert names == {"Group 1", "MixedAutoCreate"}

        for entry in data:
            if entry["labelGroup"]["labelGroupName"] == "Group 1":
                assert len(entry["labels"]) == 3
            else:
                assert entry["labels"] == []

    def test_admin_subject_override(
        self,
        client: TestClient,
        editing_scenario: DatabaseScenario,
    ) -> None:
        """Admin can use subjectId to reload another user's label data."""
        owner = _editing_user(editing_scenario, "owner")
        admin = _editing_user(editing_scenario, "admin")
        chapter = editing_scenario.chapters["chapter"]
        editing_scenario.contents["content_v1"]
        label_group = editing_scenario.label_groups["group_1"]
        editing_scenario.label_datas["group_1_data"]

        owner_response = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(label_group.label_group_id),
            headers=_auth_headers(owner),
        )
        admin_response = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(label_group.label_group_id),
            params={"subjectId": str(owner.user_id)},
            headers=_auth_headers(admin),
        )

        assert owner_response.status_code == status.HTTP_200_OK
        assert admin_response.status_code == status.HTTP_200_OK
        assert admin_response.json() == owner_response.json()

    def test_non_admin_subject_forbidden(
        self,
        client: TestClient,
        editing_scenario: DatabaseScenario,
    ) -> None:
        owner = _editing_user(editing_scenario, "owner")
        other_user = _editing_user(editing_scenario, "other")
        chapter = editing_scenario.chapters["chapter"]
        editing_scenario.contents["content_v1"]
        label_group = editing_scenario.label_groups["group_1"]
        editing_scenario.label_datas["group_1_data"]

        response = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(label_group.label_group_id),
            params={"subjectId": str(owner.user_id)},
            headers=_auth_headers(other_user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_subject_not_found(
        self,
        client: TestClient,
        editing_scenario: DatabaseScenario,
    ) -> None:
        admin = _editing_user(editing_scenario, "admin")
        chapter = editing_scenario.chapters["chapter"]
        editing_scenario.contents["content_v1"]
        label_group = editing_scenario.label_groups["group_1"]
        editing_scenario.label_datas["group_1_data"]

        response = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(label_group.label_group_id),
            params={"subjectId": str(uuid.uuid4())},
            headers=_auth_headers(admin),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_reload_idempotent(
        self,
        client: TestClient,
        editing_scenario: DatabaseScenario,
    ) -> None:
        """Reloading the same group twice returns identical results."""
        actor = _editing_user(editing_scenario, "owner")
        chapter = editing_scenario.chapters["chapter"]
        editing_scenario.contents["content_v1"]
        label_group = editing_scenario.label_groups["group_1"]
        editing_scenario.label_datas["group_1_data"]

        response1 = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(label_group.label_group_id),
            headers=_auth_headers(actor),
        )
        response2 = client.post(
            _reload_url(chapter.chapter_id),
            json=_reload_params(label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        assert response1.json() == response2.json()
