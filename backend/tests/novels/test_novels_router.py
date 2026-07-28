"""Router tests for novel endpoints."""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.main import app
from src.novels.constants import Role
from src.novels.models import Chapter, ChapterContent, Novel
from test_support.test_data.scenarios import DatabaseScenario

STARFALL_UPLOAD_ARTIFACT = (
    Path(__file__).parents[1] / "test_data" / "artifacts" / "chapter-upload" / "v1" / "starfall.json"
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


def _chapter_upload(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    return {"chapters": chapters}


def _post_chapter_upload(
    client: TestClient,
    user: User,
    novel_id: uuid.UUID,
    document: dict[str, Any] | bytes,
) -> Response:
    content = document if isinstance(document, bytes) else json.dumps(document).encode()
    return client.post(
        "/chapters/upload",
        data={"novelId": str(novel_id), "version": "v1"},
        files={"file": ("chapters.json", content, "application/json")},
        headers=_auth_headers(user),
    )


class TestReadNovelWithContributors:
    def test_owner_gets_private_novel_with_contributors(
        self, client: TestClient, novel_access_scenario: DatabaseScenario
    ) -> None:
        novel = novel_access_scenario.novels["oe"]

        response = client.get(
            _with_contributors_url(novel.novel_id), headers=_auth_headers(novel_access_scenario.users["owner"])
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["novel"]["novelId"] == str(novel.novel_id)
        assert _contributors(payload) == _expected_contributors(
            novel,
            (novel_access_scenario.users["owner"], Role.OWNER),
            (novel_access_scenario.users["other"], Role.EDITOR),
        )

    def test_editor_gets_private_novel_with_contributors(
        self, client: TestClient, novel_access_scenario: DatabaseScenario
    ) -> None:
        novel = novel_access_scenario.novels["oe"]

        response = client.get(
            _with_contributors_url(novel.novel_id), headers=_auth_headers(novel_access_scenario.users["other"])
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["novel"]["novelId"] == str(novel.novel_id)
        assert _contributors(payload) == _expected_contributors(
            novel,
            (novel_access_scenario.users["owner"], Role.OWNER),
            (novel_access_scenario.users["other"], Role.EDITOR),
        )

    def test_admin_gets_private_novel_with_contributors(
        self, client: TestClient, novel_access_scenario: DatabaseScenario
    ) -> None:
        novel = novel_access_scenario.novels["oe"]

        response = client.get(
            _with_contributors_url(novel.novel_id), headers=_auth_headers(novel_access_scenario.users["admin"])
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["novel"]["novelId"] == str(novel.novel_id)
        assert _contributors(payload) == _expected_contributors(
            novel,
            (novel_access_scenario.users["owner"], Role.OWNER),
            (novel_access_scenario.users["other"], Role.EDITOR),
        )

    def test_non_contributor_cannot_get_private_novel_with_contributors(
        self, client: TestClient, novel_access_scenario: DatabaseScenario
    ) -> None:
        novel = novel_access_scenario.novels["prt"]

        response = client.get(
            _with_contributors_url(novel.novel_id), headers=_auth_headers(novel_access_scenario.users["other"])
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_missing_novel_returns_404(self, client: TestClient, novel_access_scenario: DatabaseScenario) -> None:
        response = client.get(
            _with_contributors_url(uuid.uuid4()), headers=_auth_headers(novel_access_scenario.users["owner"])
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCreateChaptersByUpload:
    def test_owner_uploads_chapters_and_initial_content_atomically(
        self, client: TestClient, test_db: Session, novel_access_scenario: DatabaseScenario
    ) -> None:
        novel = novel_access_scenario.novels["prt"]
        request = json.loads(STARFALL_UPLOAD_ARTIFACT.read_text(encoding="utf-8"))

        response = _post_chapter_upload(client, novel_access_scenario.users["owner"], novel.novel_id, request)

        assert response.status_code == status.HTTP_200_OK
        response_by_num = {chapter["chapterNum"]: chapter for chapter in response.json()}
        assert set(response_by_num) == {1, 2, 3, 4}
        assert response_by_num[1]["chapterTitle"] == "Chapter 1"
        assert response_by_num[1]["chapterIsPublic"] is True

        chapters = test_db.scalars(
            select(Chapter).where(Chapter.novel_id == novel.novel_id).order_by(Chapter.chapter_num)
        ).all()
        assert [chapter.chapter_num for chapter in chapters] == [1, 2, 3, 4]

        contents = test_db.scalars(
            select(ChapterContent).where(ChapterContent.chapter_id.in_([chapter.chapter_id for chapter in chapters]))
        ).all()
        expected_texts = {chapter["chapterContentText"] for chapter in request["chapters"]}
        assert {content.chapter_content_text for content in contents} == expected_texts
        assert {content.chapter_content_version for content in contents} == {1}

    def test_duplicate_chapter_numbers_return_conflict_without_partial_insert(
        self, client: TestClient, test_db: Session, novel_access_scenario: DatabaseScenario
    ) -> None:
        novel = novel_access_scenario.novels["prt"]
        request = _chapter_upload(
            [
                {"chapterNum": 201, "chapterContentText": "First duplicate."},
                {"chapterNum": 201, "chapterContentText": "Second duplicate."},
            ],
        )

        response = _post_chapter_upload(client, novel_access_scenario.users["owner"], novel.novel_id, request)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            test_db.scalars(select(Chapter).where(Chapter.novel_id == novel.novel_id, Chapter.chapter_num == 201)).all()
            == []
        )

    def test_viewer_cannot_upload_chapters(
        self, client: TestClient, test_db: Session, novel_access_scenario: DatabaseScenario
    ) -> None:
        novel = novel_access_scenario.novels["ov"]
        request = _chapter_upload([{"chapterNum": 301, "chapterContentText": "Denied."}])

        response = _post_chapter_upload(client, novel_access_scenario.users["other"], novel.novel_id, request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert (
            test_db.scalars(select(Chapter).where(Chapter.novel_id == novel.novel_id, Chapter.chapter_num == 301)).all()
            == []
        )

    def test_admin_upload_to_missing_novel_returns_not_found(
        self, client: TestClient, novel_access_scenario: DatabaseScenario
    ) -> None:
        missing_novel_id = uuid.uuid4()
        request = _chapter_upload([{"chapterNum": 401, "chapterContentText": "Missing."}])

        response = _post_chapter_upload(client, novel_access_scenario.users["admin"], missing_novel_id, request)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_empty_upload_returns_validation_error(
        self, client: TestClient, novel_access_scenario: DatabaseScenario
    ) -> None:
        response = _post_chapter_upload(
            client,
            novel_access_scenario.users["owner"],
            novel_access_scenario.novels["prt"].novel_id,
            _chapter_upload([]),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_json_upload_returns_bad_request(
        self, client: TestClient, novel_access_scenario: DatabaseScenario
    ) -> None:
        response = _post_chapter_upload(
            client, novel_access_scenario.users["owner"], novel_access_scenario.novels["prt"].novel_id, b'{"chapters":'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_file_field_returns_validation_error(
        self, client: TestClient, novel_access_scenario: DatabaseScenario
    ) -> None:
        response = client.post(
            "/chapters/upload",
            data={"novelId": str(novel_access_scenario.novels["prt"].novel_id), "version": "v1"},
            headers=_auth_headers(novel_access_scenario.users["owner"]),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_openapi_contract_documents_upload_responses(self) -> None:
        openapi = app.openapi()
        operation = openapi["paths"]["/chapters/upload"]["post"]

        assert set(operation["responses"]) == {"200", "400", "401", "404", "409", "422"}
        for response_code in ("400", "401", "404", "409"):
            schema = operation["responses"][response_code]["content"]["application/json"]["schema"]
            assert schema == {"$ref": "#/components/schemas/DetailHTTPErrorResponse"}

        request_schema = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
        schema_name = request_schema["$ref"].rsplit("/", maxsplit=1)[-1]
        multipart_schema = openapi["components"]["schemas"][schema_name]
        assert set(multipart_schema["required"]) == {"novelId", "version", "file"}
        assert multipart_schema["properties"]["version"]["const"] == "v1"
        assert multipart_schema["properties"]["file"]["format"] == "binary"
