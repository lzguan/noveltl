"""Router tests for novel endpoints."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.auth.models import User
from src.auth.utils import create_access_token
from src.novels.constants import Role
from src.novels.models import Novel
from tests.gate_logging import log_gate

pytestmark = pytest.mark.dependency(
    depends=["gate::fixture_validation", "gate::novels::permissions"],
    scope="session",
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _with_contributors_url(novel_id: uuid.UUID) -> str:
    return f"/novels/{novel_id}/with-contributors"


def _contributors(payload: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (entry["userId"], entry["novelId"], entry["contributorRole"])
        for entry in payload["users"]
        if isinstance(entry, dict)
    }


def _expected_contributors(novel: Novel, *users_and_roles: tuple[User, Role]) -> set[tuple[str, str, str]]:
    return {(str(user.user_id), str(novel.novel_id), role.value) for user, role in users_and_roles}


class TestReadNovelWithContributors:
    @pytest.mark.dependency(name="novels::router::with_contributors_owner", scope="session")
    def test_owner_gets_private_novel_with_contributors(
        self,
        client: TestClient,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ) -> None:
        novel = p1_novels["oe"]

        response = client.get(_with_contributors_url(novel.novel_id), headers=_auth_headers(p1_user_1))

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["novel"]["novelId"] == str(novel.novel_id)
        assert _contributors(payload) == _expected_contributors(
            novel,
            (p1_user_1, Role.OWNER),
            (p1_user_2, Role.EDITOR),
        )

    @pytest.mark.dependency(name="novels::router::with_contributors_editor", scope="session")
    def test_editor_gets_private_novel_with_contributors(
        self,
        client: TestClient,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ) -> None:
        novel = p1_novels["oe"]

        response = client.get(_with_contributors_url(novel.novel_id), headers=_auth_headers(p1_user_2))

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["novel"]["novelId"] == str(novel.novel_id)
        assert _contributors(payload) == _expected_contributors(
            novel,
            (p1_user_1, Role.OWNER),
            (p1_user_2, Role.EDITOR),
        )

    @pytest.mark.dependency(name="novels::router::with_contributors_admin", scope="session")
    def test_admin_gets_private_novel_with_contributors(
        self,
        client: TestClient,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
        p1_admin: User,
    ) -> None:
        novel = p1_novels["oe"]

        response = client.get(_with_contributors_url(novel.novel_id), headers=_auth_headers(p1_admin))

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["novel"]["novelId"] == str(novel.novel_id)
        assert _contributors(payload) == _expected_contributors(
            novel,
            (p1_user_1, Role.OWNER),
            (p1_user_2, Role.EDITOR),
        )

    @pytest.mark.dependency(name="novels::router::with_contributors_non_contributor_404", scope="session")
    def test_non_contributor_cannot_get_private_novel_with_contributors(
        self,
        client: TestClient,
        p1_novels: dict[str, Novel],
        p1_user_2: User,
    ) -> None:
        novel = p1_novels["prt"]

        response = client.get(_with_contributors_url(novel.novel_id), headers=_auth_headers(p1_user_2))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.dependency(name="novels::router::with_contributors_missing_404", scope="session")
    def test_missing_novel_returns_404(self, client: TestClient, p1_user_1: User) -> None:
        response = client.get(_with_contributors_url(uuid.uuid4()), headers=_auth_headers(p1_user_1))

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.dependency(
    name="gate::novels::router",
    depends=[
        "novels::router::with_contributors_owner",
        "novels::router::with_contributors_editor",
        "novels::router::with_contributors_admin",
        "novels::router::with_contributors_non_contributor_404",
        "novels::router::with_contributors_missing_404",
    ],
    scope="session",
)
def test_gate() -> None:
    """All novel router tests must pass before downstream layers run."""
    log_gate("gate::novels::router")
