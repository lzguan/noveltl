from datetime import timedelta

from fastapi import status
from fastapi.testclient import TestClient

from src.auth.models import User
from src.auth.utils import create_access_token
from test_support.test_data.scenarios import DatabaseScenario


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _contributors_url(label_group_id: object) -> str:
    return f"/label-groups/{label_group_id}/contributors"


def _label_groups_with_role_url(novel_id: object) -> str:
    return f"/label-groups-with-role?novelId={novel_id}"


def _label_url(label_id: object) -> str:
    return f"/labels/{label_id}"


class TestReadLabel:
    def test_owner_can_read_label(self, client: TestClient, label_access_scenario: DatabaseScenario) -> None:
        actor = label_access_scenario.users["owner"]
        label = label_access_scenario.labels["owner_test"]

        response = client.get(_label_url(label.label_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "labelDataId": str(label.label_data_id),
            "labelDirty": label.label_dirty,
            "labelEnd": label.label_end,
            "labelEntityGroup": label.label_entity_group,
            "labelId": str(label.label_id),
            "labelScore": label.label_score,
            "labelStart": label.label_start,
            "labelWord": label.label_word,
        }

    def test_viewer_can_read_label(self, client: TestClient, label_access_scenario: DatabaseScenario) -> None:
        actor = label_access_scenario.users["collaborator"]
        label = label_access_scenario.labels["viewer_test"]

        response = client.get(_label_url(label.label_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["labelId"] == str(label.label_id)

    def test_non_contributor_gets_404(self, client: TestClient, label_access_scenario: DatabaseScenario) -> None:
        actor = label_access_scenario.users["outsider"]
        label = label_access_scenario.labels["owner_test"]

        response = client.get(_label_url(label.label_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Label not found."

    def test_missing_label_gets_404(self, client: TestClient, label_access_scenario: DatabaseScenario) -> None:
        actor = label_access_scenario.users["owner"]

        response = client.get(
            _label_url("00000000-0000-0000-0000-000000000000"),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Label not found."


class TestReadLabelGroupsWithRole:
    def test_owner_can_read_label_groups_with_role(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        actor = label_access_scenario.users["owner"]
        novel = label_access_scenario.novels["public"]

        response = client.get(_label_groups_with_role_url(novel.novel_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert {(entry["labelGroup"]["labelGroupName"], entry["role"]) for entry in payload} == {
            ("Owner Only Group", "owner"),
            ("With Editor Group", "owner"),
            ("With Viewer Group", "owner"),
        }

    def test_editor_and_viewer_can_read_label_groups_with_role(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        actor = label_access_scenario.users["collaborator"]
        novel = label_access_scenario.novels["public"]

        response = client.get(_label_groups_with_role_url(novel.novel_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert {(entry["labelGroup"]["labelGroupName"], entry["role"]) for entry in payload} == {
            ("With Editor Group", "editor"),
            ("With Viewer Group", "viewer"),
        }

    def test_non_contributor_reads_no_label_groups_with_role(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        actor = label_access_scenario.users["outsider"]
        novel = label_access_scenario.novels["public"]

        response = client.get(_label_groups_with_role_url(novel.novel_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_admin_can_read_label_groups_with_role(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        actor = label_access_scenario.users["admin"]
        novel = label_access_scenario.novels["public"]

        response = client.get(_label_groups_with_role_url(novel.novel_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload == []


class TestReadLabelContributors:
    def test_owner_can_read_contributors(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        actor = label_access_scenario.users["owner"]
        label_group = label_access_scenario.label_groups["owner_only"]

        response = client.get(
            _contributors_url(label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload == [
            {
                "labelContributorRole": "owner",
                "labelGroupId": str(label_group.label_group_id),
                "userId": str(actor.user_id),
            }
        ]

    def test_viewer_can_read_all_group_contributors(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_viewer"]

        response = client.get(
            _contributors_url(label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert {(entry["userId"], entry["labelContributorRole"]) for entry in payload} == {
            (str(label_access_scenario.users["owner"].user_id), "owner"),
            (str(label_access_scenario.users["collaborator"].user_id), "viewer"),
        }
        assert {entry["labelGroupId"] for entry in payload} == {str(label_group.label_group_id)}

    def test_non_contributor_gets_404(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        actor = label_access_scenario.users["outsider"]
        label_group = label_access_scenario.label_groups["owner_only"]

        response = client.get(
            _contributors_url(label_group.label_group_id),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == f"Label group with id {label_group.label_group_id} not found."

    def test_missing_group_gets_404(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        actor = label_access_scenario.users["owner"]

        response = client.get(
            _contributors_url("00000000-0000-0000-0000-000000000000"),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Label group with id 00000000-0000-0000-0000-000000000000 not found."
