"""Router tests for novel endpoints."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.main import app
from src.novels.constants import Role
from src.novels.models import Chapter, ChapterContent, Novel
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


def _chapter_upload(novel_id: uuid.UUID, chapters: list[dict[str, Any]]) -> dict[str, Any]:
    return {"version": "v1", "novelId": str(novel_id), "chapters": chapters}


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


class TestCreateChaptersByUpload:
    @pytest.mark.dependency(name="novels::router::chapter_upload_success", scope="session")
    def test_owner_uploads_chapters_and_initial_content_atomically(
        self,
        client: TestClient,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ) -> None:
        novel = p1_novels["prt"]
        request = _chapter_upload(
            novel.novel_id,
            [
                {
                    "chapterNum": 101,
                    "chapterTitle": "Arrival",
                    "chapterContentText": "The first uploaded chapter.",
                    "chapterIsPublic": True,
                },
                {
                    "chapterNum": 102,
                    "chapterContentText": "",
                },
            ],
        )

        response = client.post("/chapters/upload", json=request, headers=_auth_headers(p1_user_1))

        assert response.status_code == status.HTTP_200_OK
        response_by_num = {chapter["chapterNum"]: chapter for chapter in response.json()}
        assert response_by_num[101]["chapterTitle"] == "Arrival"
        assert response_by_num[101]["chapterIsPublic"] is True
        assert response_by_num[102]["chapterTitle"] == "Chapter 102"
        assert response_by_num[102]["chapterIsPublic"] is False

        chapters = test_db.scalars(
            select(Chapter).where(Chapter.novel_id == novel.novel_id).order_by(Chapter.chapter_num)
        ).all()
        assert [chapter.chapter_num for chapter in chapters] == [101, 102]

        contents = test_db.scalars(
            select(ChapterContent)
            .where(ChapterContent.chapter_id.in_([chapter.chapter_id for chapter in chapters]))
            .order_by(ChapterContent.chapter_content_text)
        ).all()
        assert {(content.chapter_content_text, content.chapter_content_version) for content in contents} == {
            ("", 1),
            ("The first uploaded chapter.", 1),
        }

    @pytest.mark.dependency(name="novels::router::chapter_upload_duplicate", scope="session")
    def test_duplicate_chapter_numbers_return_conflict_without_partial_insert(
        self,
        client: TestClient,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ) -> None:
        novel = p1_novels["prt"]
        request = _chapter_upload(
            novel.novel_id,
            [
                {"chapterNum": 201, "chapterContentText": "First duplicate."},
                {"chapterNum": 201, "chapterContentText": "Second duplicate."},
            ],
        )

        response = client.post("/chapters/upload", json=request, headers=_auth_headers(p1_user_1))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert test_db.scalars(
            select(Chapter).where(Chapter.novel_id == novel.novel_id, Chapter.chapter_num == 201)
        ).all() == []

    @pytest.mark.dependency(name="novels::router::chapter_upload_permissions", scope="session")
    def test_viewer_cannot_upload_chapters(
        self,
        client: TestClient,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_2: User,
    ) -> None:
        novel = p1_novels["ov"]
        request = _chapter_upload(novel.novel_id, [{"chapterNum": 301, "chapterContentText": "Denied."}])

        response = client.post("/chapters/upload", json=request, headers=_auth_headers(p1_user_2))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert test_db.scalars(
            select(Chapter).where(Chapter.novel_id == novel.novel_id, Chapter.chapter_num == 301)
        ).all() == []

    @pytest.mark.dependency(name="novels::router::chapter_upload_missing", scope="session")
    def test_admin_upload_to_missing_novel_returns_not_found(self, client: TestClient, p1_admin: User) -> None:
        request = _chapter_upload(uuid.uuid4(), [{"chapterNum": 401, "chapterContentText": "Missing."}])

        response = client.post("/chapters/upload", json=request, headers=_auth_headers(p1_admin))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.dependency(name="novels::router::chapter_upload_validation", scope="session")
    def test_empty_upload_returns_validation_error(
        self,
        client: TestClient,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ) -> None:
        response = client.post(
            "/chapters/upload",
            json=_chapter_upload(p1_novels["prt"].novel_id, []),
            headers=_auth_headers(p1_user_1),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.dependency(name="novels::router::chapter_upload_contract", scope="session")
    def test_openapi_contract_documents_upload_responses(self) -> None:
        operation = app.openapi()["paths"]["/chapters/upload"]["post"]

        assert set(operation["responses"]) == {"200", "400", "401", "404", "409", "422"}
        for response_code in ("400", "401", "404", "409"):
            schema = operation["responses"][response_code]["content"]["application/json"]["schema"]
            assert schema == {"$ref": "#/components/schemas/DetailHTTPErrorResponse"}

@pytest.mark.dependency(
    name="gate::novels::router",
    depends=[
        "novels::router::with_contributors_owner",
        "novels::router::with_contributors_editor",
        "novels::router::with_contributors_admin",
        "novels::router::with_contributors_non_contributor_404",
        "novels::router::with_contributors_missing_404",
        "novels::router::chapter_upload_success",
        "novels::router::chapter_upload_duplicate",
        "novels::router::chapter_upload_permissions",
        "novels::router::chapter_upload_missing",
        "novels::router::chapter_upload_validation",
        "novels::router::chapter_upload_contract",
    ],
    scope="session",
)
def test_gate() -> None:
    """All novel router tests must pass before downstream layers run."""
    log_gate("gate::novels::router")
