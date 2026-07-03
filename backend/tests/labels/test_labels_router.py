from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.auth.models import User
from src.auth.utils import create_access_token
from tests.fixtures.bundles import LabelFixtureBundle, ScenarioBundle
from tests.gate_logging import log_gate

pytestmark = pytest.mark.dependency(
    depends=["gate::fixture_validation", "gate::labels::permissions", "gate::novels::permissions"],
    scope="session",
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _label_access_user(bundle: ScenarioBundle, user_name: str) -> User:
    return bundle.users.by_name[user_name]


def _label_access_group(bundle: ScenarioBundle, group_name: str) -> LabelFixtureBundle:
    return bundle.label_groups_by_name[group_name]


def _contributors_url(label_group_id: object) -> str:
    return f"/label-groups/{label_group_id}/contributors"


def _label_groups_with_role_url(novel_id: object) -> str:
    return f"/label-groups-with-role?novelId={novel_id}"


class TestReadLabelGroupsWithRole:
    @pytest.mark.dependency(name="labels::router::owner_can_read_label_groups_with_role", scope="session")
    def test_owner_can_read_label_groups_with_role(
        self,
        client: TestClient,
        label_access_scenario: ScenarioBundle,
    ) -> None:
        actor = _label_access_user(label_access_scenario, "lp_alice")
        novel = label_access_scenario.novels_by_title["LP Public Novel"].novel

        response = client.get(_label_groups_with_role_url(novel.novel_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert {
            (entry["labelGroup"]["labelGroupName"], entry["role"])
            for entry in payload
        } == {
            ("Owner Only Group", "owner"),
            ("With Editor Group", "owner"),
            ("With Viewer Group", "owner"),
        }

    @pytest.mark.dependency(name="labels::router::editor_and_viewer_can_read_label_groups_with_role", scope="session")
    def test_editor_and_viewer_can_read_label_groups_with_role(
        self,
        client: TestClient,
        label_access_scenario: ScenarioBundle,
    ) -> None:
        actor = _label_access_user(label_access_scenario, "lp_bob")
        novel = label_access_scenario.novels_by_title["LP Public Novel"].novel

        response = client.get(_label_groups_with_role_url(novel.novel_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert {
            (entry["labelGroup"]["labelGroupName"], entry["role"])
            for entry in payload
        } == {
            ("With Editor Group", "editor"),
            ("With Viewer Group", "viewer"),
        }

    @pytest.mark.dependency(name="labels::router::non_contributor_reads_no_label_groups_with_role", scope="session")
    def test_non_contributor_reads_no_label_groups_with_role(
        self,
        client: TestClient,
        label_access_scenario: ScenarioBundle,
    ) -> None:
        actor = _label_access_user(label_access_scenario, "lp_charlie")
        novel = label_access_scenario.novels_by_title["LP Public Novel"].novel

        response = client.get(_label_groups_with_role_url(novel.novel_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.dependency(name="labels::router::admin_can_read_label_groups_with_role", scope="session")
    def test_admin_can_read_label_groups_with_role(
        self,
        client: TestClient,
        label_access_scenario: ScenarioBundle,
    ) -> None:
        actor = _label_access_user(label_access_scenario, "lp_admin")
        novel = label_access_scenario.novels_by_title["LP Public Novel"].novel

        response = client.get(_label_groups_with_role_url(novel.novel_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload == []

    @pytest.mark.dependency(
        name="gate::labels::router::label_groups_with_role",
        depends=[
            "labels::router::owner_can_read_label_groups_with_role",
            "labels::router::editor_and_viewer_can_read_label_groups_with_role",
            "labels::router::non_contributor_reads_no_label_groups_with_role",
            "labels::router::admin_can_read_label_groups_with_role",
        ],
        scope="session",
    )
    def test_class_gate(self) -> None:
        pass


class TestReadLabelContributors:
    @pytest.mark.dependency(name="labels::router::owner_can_read_contributors", scope="session")
    def test_owner_can_read_contributors(
        self,
        client: TestClient,
        label_access_scenario: ScenarioBundle,
    ) -> None:
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")

        response = client.get(
            _contributors_url(label_group.label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload == [
            {
                "labelContributorRole": "owner",
                "labelGroupId": str(label_group.label_group.label_group_id),
                "userId": str(actor.user_id),
            }
        ]

    @pytest.mark.dependency(name="labels::router::viewer_can_read_all_group_contributors", scope="session")
    def test_viewer_can_read_all_group_contributors(
        self,
        client: TestClient,
        label_access_scenario: ScenarioBundle,
    ) -> None:
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Viewer Group")

        response = client.get(
            _contributors_url(label_group.label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert {(entry["userId"], entry["labelContributorRole"]) for entry in payload} == {
            (str(user.user_id), "owner") for user in label_group.owner_users
        } | {(str(user.user_id), "viewer") for user in label_group.viewer_users}
        assert {entry["labelGroupId"] for entry in payload} == {str(label_group.label_group.label_group_id)}

    @pytest.mark.dependency(name="labels::router::non_contributor_gets_404", scope="session")
    def test_non_contributor_gets_404(
        self,
        client: TestClient,
        label_access_scenario: ScenarioBundle,
    ) -> None:
        actor = _label_access_user(label_access_scenario, "lp_charlie")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")

        response = client.get(
            _contributors_url(label_group.label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == f"Label group with id {label_group.label_group.label_group_id} not found."

    @pytest.mark.dependency(name="labels::router::missing_group_gets_404", scope="session")
    def test_missing_group_gets_404(
        self,
        client: TestClient,
        label_access_scenario: ScenarioBundle,
    ) -> None:
        actor = _label_access_user(label_access_scenario, "lp_alice")

        response = client.get(
            _contributors_url("00000000-0000-0000-0000-000000000000"),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Label group with id 00000000-0000-0000-0000-000000000000 not found."

    @pytest.mark.dependency(
        name="gate::labels::router::contributors",
        depends=[
            "labels::router::owner_can_read_contributors",
            "labels::router::viewer_can_read_all_group_contributors",
            "labels::router::non_contributor_gets_404",
            "labels::router::missing_group_gets_404",
        ],
        scope="session",
    )
    def test_class_gate(self) -> None:
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::labels::router",
    depends=[
        "gate::labels::router::label_groups_with_role",
        "gate::labels::router::contributors",
    ],
    scope="session",
)
def test_gate() -> None:
    log_gate("gate::labels::router")
