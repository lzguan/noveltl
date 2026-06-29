"""Router tests for the editing aggregate endpoint."""

import uuid
from datetime import timedelta
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


def _eager_params(bundle: ScenarioBundle, *names: str) -> list[str]:
    """Build eager query param values from label group names in the scenario."""
    return [str(bundle.label_groups_by_name[name].label_group.label_group_id) for name in names]


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
    @pytest.mark.dependency(name="editing::router::owner_happy_path", scope="session")
    def test_owner_happy_path(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        actor = _versioned_user(versioned_chapter_scenario, "to_user")
        chapter_bundle = versioned_chapter_scenario.chapters[0]

        response = client.post(
            _editing_url(chapter_bundle.chapter.chapter_id),
            json=_eager_params(versioned_chapter_scenario, "Group 1", "Group 2"),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()

        assert payload["chapterContent"]["chapterContentId"] == str(chapter_bundle.latest_content.chapter_content_id)

        assert {e["labelGroup"]["labelGroupName"] for e in payload["eagerLabelData"]} == {"Group 1", "Group 2"}
        for entry in payload["eagerLabelData"]:
            assert len(entry["labels"]) > 0

        assert payload["lazyLabelData"] == []
        assert payload["noLabelData"] == []

    @pytest.mark.dependency(name="editing::router::admin_subject_override", scope="session")
    def test_admin_subject_override(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        owner = _versioned_user(versioned_chapter_scenario, "to_user")
        admin = _versioned_user(versioned_chapter_scenario, "to_admin")
        chapter_bundle = versioned_chapter_scenario.chapters[0]

        eager = _eager_params(versioned_chapter_scenario, "Group 1", "Group 2")
        owner_response = client.post(
            _editing_url(chapter_bundle.chapter.chapter_id),
            json=eager,
            headers=_auth_headers(owner),
        )
        admin_response = client.post(
            _editing_url(chapter_bundle.chapter.chapter_id),
            json=eager,
            params={"subjectId": str(owner.user_id)},
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

        response = client.post(
            _editing_url(chapter_bundle.chapter.chapter_id),
            json=_eager_params(versioned_chapter_scenario, "Group 1", "Group 2"),
            params={"subjectId": str(owner.user_id)},
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

        response = client.post(
            _editing_url(chapter_bundle.chapter.chapter_id),
            json=_eager_params(versioned_chapter_scenario, "Group 1", "Group 2"),
            params={"subjectId": str(uuid.uuid4())},
            headers=_auth_headers(admin),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.dependency(name="editing::router::cap_consistency", scope="session")
    def test_eager_lazy_no_split(
        self,
        client: TestClient,
        test_db: Session,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        actor = _versioned_user(versioned_chapter_scenario, "to_user")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        novel_bundle = versioned_chapter_scenario.novels[0]

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

        # Eager: only Group 1 and Group 3
        response = client.post(
            _editing_url(chapter_bundle.chapter.chapter_id),
            json=[
                str(versioned_chapter_scenario.label_groups_by_name["Group 1"].label_group.label_group_id),
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


def _reload_url(chapter_id: uuid.UUID) -> str:
    return f"/edit-chapter-data/{chapter_id}/label-data"


def _reload_params(*label_group_ids: uuid.UUID) -> list[str]:
    return [str(gid) for gid in label_group_ids]


class TestReadEditChapterLabelData:
    """Tests for the reload-group endpoint that fetches / lazily creates LabelData."""

    @pytest.mark.dependency(name="editing::router::reload_existing", scope="session")
    def test_reload_existing(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        """Reloading a group that already has LabelData returns its labels."""
        actor = _versioned_user(versioned_chapter_scenario, "to_user")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        lg1 = versioned_chapter_scenario.label_groups_by_name["Group 1"]

        response = client.post(
            _reload_url(chapter_bundle.chapter.chapter_id),
            json=_reload_params(lg1.label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        entry = data[0]
        assert entry["labelGroup"]["labelGroupName"] == "Group 1"
        assert entry["labelData"]["labelGroupId"] == str(lg1.label_group.label_group_id)
        assert len(entry["labels"]) == 3

    @pytest.mark.dependency(name="editing::router::reload_auto_create", scope="session")
    def test_reload_auto_create(
        self,
        client: TestClient,
        test_db: Session,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        """Reloading a group without LabelData auto-creates it for editors."""
        actor = _versioned_user(versioned_chapter_scenario, "to_user")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        novel_bundle = versioned_chapter_scenario.novels[0]

        new_group = LabelGroup(label_group_name="ReloadAutoCreate", novel_id=novel_bundle.novel.novel_id)
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
                LabelData.chapter_content_id == chapter_bundle.latest_content.chapter_content_id,
            )
            .first()
            is None
        )

        response = client.post(
            _reload_url(chapter_bundle.chapter.chapter_id),
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
                LabelData.chapter_content_id == chapter_bundle.latest_content.chapter_content_id,
            )
            .first()
        )
        assert ld is not None
        assert str(ld.label_data_id) == entry["labelData"]["labelDataId"]

    @pytest.mark.dependency(name="editing::router::reload_viewer_no_create", scope="session")
    def test_reload_viewer_no_auto_create(
        self,
        client: TestClient,
        test_db: Session,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        """A viewer should not trigger auto-create — the group is silently excluded."""
        actor = _versioned_user(versioned_chapter_scenario, "to_user")
        viewer = _versioned_user(versioned_chapter_scenario, "to_other")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        novel_bundle = versioned_chapter_scenario.novels[0]

        new_group = LabelGroup(label_group_name="ViewerNoCreate", novel_id=novel_bundle.novel.novel_id)
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
            _reload_url(chapter_bundle.chapter.chapter_id),
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
                LabelData.chapter_content_id == chapter_bundle.latest_content.chapter_content_id,
            )
            .first()
            is None
        )

    @pytest.mark.dependency(name="editing::router::reload_mixed", scope="session")
    def test_reload_mixed(
        self,
        client: TestClient,
        test_db: Session,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        """Mix of groups with existing LabelData and one needing auto-create."""
        actor = _versioned_user(versioned_chapter_scenario, "to_user")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        novel_bundle = versioned_chapter_scenario.novels[0]
        lg1 = versioned_chapter_scenario.label_groups_by_name["Group 1"]

        new_group = LabelGroup(label_group_name="MixedAutoCreate", novel_id=novel_bundle.novel.novel_id)
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
            _reload_url(chapter_bundle.chapter.chapter_id),
            json=_reload_params(lg1.label_group.label_group_id, new_group.label_group_id),
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

    @pytest.mark.dependency(name="editing::router::reload_admin_subject", scope="session")
    def test_admin_subject_override(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        """Admin can use subjectId to reload another user's label data."""
        owner = _versioned_user(versioned_chapter_scenario, "to_user")
        admin = _versioned_user(versioned_chapter_scenario, "to_admin")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        lg1 = versioned_chapter_scenario.label_groups_by_name["Group 1"]

        owner_response = client.post(
            _reload_url(chapter_bundle.chapter.chapter_id),
            json=_reload_params(lg1.label_group.label_group_id),
            headers=_auth_headers(owner),
        )
        admin_response = client.post(
            _reload_url(chapter_bundle.chapter.chapter_id),
            json=_reload_params(lg1.label_group.label_group_id),
            params={"subjectId": str(owner.user_id)},
            headers=_auth_headers(admin),
        )

        assert owner_response.status_code == status.HTTP_200_OK
        assert admin_response.status_code == status.HTTP_200_OK
        assert admin_response.json() == owner_response.json()

    @pytest.mark.dependency(name="editing::router::reload_non_admin_subject_forbidden", scope="session")
    def test_non_admin_subject_forbidden(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        owner = _versioned_user(versioned_chapter_scenario, "to_user")
        other_user = _versioned_user(versioned_chapter_scenario, "to_other")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        lg1 = versioned_chapter_scenario.label_groups_by_name["Group 1"]

        response = client.post(
            _reload_url(chapter_bundle.chapter.chapter_id),
            json=_reload_params(lg1.label_group.label_group_id),
            params={"subjectId": str(owner.user_id)},
            headers=_auth_headers(other_user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.dependency(name="editing::router::reload_admin_subject_not_found", scope="session")
    def test_admin_subject_not_found(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        admin = _versioned_user(versioned_chapter_scenario, "to_admin")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        lg1 = versioned_chapter_scenario.label_groups_by_name["Group 1"]

        response = client.post(
            _reload_url(chapter_bundle.chapter.chapter_id),
            json=_reload_params(lg1.label_group.label_group_id),
            params={"subjectId": str(uuid.uuid4())},
            headers=_auth_headers(admin),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.dependency(name="editing::router::reload_idempotent", scope="session")
    def test_reload_idempotent(
        self,
        client: TestClient,
        versioned_chapter_scenario: ScenarioBundle,
    ) -> None:
        """Reloading the same group twice returns identical results."""
        actor = _versioned_user(versioned_chapter_scenario, "to_user")
        chapter_bundle = versioned_chapter_scenario.chapters[0]
        lg1 = versioned_chapter_scenario.label_groups_by_name["Group 1"]

        response1 = client.post(
            _reload_url(chapter_bundle.chapter.chapter_id),
            json=_reload_params(lg1.label_group.label_group_id),
            headers=_auth_headers(actor),
        )
        response2 = client.post(
            _reload_url(chapter_bundle.chapter.chapter_id),
            json=_reload_params(lg1.label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        assert response1.json() == response2.json()

    @pytest.mark.dependency(
        name="gate::editing::router::read_edit_chapter_label_data",
        depends=[
            "editing::router::reload_existing",
            "editing::router::reload_auto_create",
            "editing::router::reload_viewer_no_create",
            "editing::router::reload_mixed",
            "editing::router::reload_admin_subject",
            "editing::router::reload_non_admin_subject_forbidden",
            "editing::router::reload_admin_subject_not_found",
            "editing::router::reload_idempotent",
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
        "gate::editing::router::read_edit_chapter_label_data",
    ],
    scope="session",
)
def test_gate() -> None:
    """All editing router tests must pass before downstream layers run."""
    log_gate("gate::editing::router")
