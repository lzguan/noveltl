"""Router tests for novel endpoints."""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx2 import Response
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

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        errors = response.json()["detail"]
        assert isinstance(errors, list) and len(errors) >= 1
        assert all("input" not in err and "url" not in err for err in errors)

    def test_invalid_json_upload_returns_validation_error_without_echoing_body(
        self, client: TestClient, novel_access_scenario: DatabaseScenario
    ) -> None:
        secret_snippet = "SECRET_UPLOAD_BODY_SHOULD_NOT_ECHO"
        response = _post_chapter_upload(
            client,
            novel_access_scenario.users["owner"],
            novel_access_scenario.novels["prt"].novel_id,
            f'{{"chapters": "{secret_snippet}'.encode(),
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert secret_snippet not in response.text
        errors = response.json()["detail"]
        assert all("input" not in err and "url" not in err for err in errors)

    def test_chunked_upload_commits_and_rolls_back_atomically(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        novel_access_scenario: DatabaseScenario,
    ) -> None:
        from src.novels import imports as novel_imports

        monkeypatch.setattr(novel_imports, "UPLOAD_BATCH_SIZE", 2)
        novel_id = novel_access_scenario.novels["prt"].novel_id
        owner = novel_access_scenario.users["owner"]

        ok_response = _post_chapter_upload(
            client,
            owner,
            novel_id,
            _chapter_upload([{"chapterNum": 600 + i, "chapterContentText": f"Body {i}"} for i in range(5)]),
        )
        assert ok_response.status_code == status.HTTP_200_OK
        assert [chapter["chapterNum"] for chapter in ok_response.json()] == [600, 601, 602, 603, 604]

        # A duplicate in the second batch rolls back the first batch too.
        conflict_response = _post_chapter_upload(
            client,
            owner,
            novel_id,
            _chapter_upload(
                [
                    {"chapterNum": 700, "chapterContentText": "First batch"},
                    {"chapterNum": 701, "chapterContentText": "First batch 2"},
                    {"chapterNum": 600, "chapterContentText": "Duplicate in second batch"},
                ]
            ),
        )
        assert conflict_response.status_code == status.HTTP_409_CONFLICT
        chapters_response = client.get("/chapters", params={"novelId": str(novel_id)}, headers=_auth_headers(owner))
        chapter_nums = {chapter["chapterNum"] for chapter in chapters_response.json()}
        assert 700 not in chapter_nums and 701 not in chapter_nums

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


class TestUpdateChaptersVisibility:
    def test_owner_and_editor_update_range_and_all_chapters(
        self, client: TestClient, test_db: Session, novel_access_scenario: DatabaseScenario
    ) -> None:
        novel = novel_access_scenario.novels["oe"]
        for num in (1, 2, 3, 4):
            test_db.add(
                Chapter(novel_id=novel.novel_id, chapter_num=num, chapter_title=f"Ch {num}", chapter_is_public=False)
            )
        test_db.commit()

        publish_range = client.post(
            f"/novels/{novel.novel_id}/chapters/visibility",
            json={"start": 2, "end": 3, "isPublic": True},
            headers=_auth_headers(novel_access_scenario.users["owner"]),
        )
        assert publish_range.status_code == status.HTTP_200_OK
        assert publish_range.json() == {"updatedChapterNums": [2, 3], "isPublic": True}

        chapters = test_db.scalars(
            select(Chapter).where(Chapter.novel_id == novel.novel_id).order_by(Chapter.chapter_num)
        ).all()
        assert [(chapter.chapter_num, chapter.chapter_is_public) for chapter in chapters] == [
            (1, False),
            (2, True),
            (3, True),
            (4, False),
        ]

        # Editor can update all chapters when start/end are omitted.
        publish_all = client.post(
            f"/novels/{novel.novel_id}/chapters/visibility",
            json={"isPublic": True},
            headers=_auth_headers(novel_access_scenario.users["other"]),
        )
        assert publish_all.status_code == status.HTTP_200_OK
        assert publish_all.json() == {"updatedChapterNums": [1, 2, 3, 4], "isPublic": True}

        unpublish_single = client.post(
            f"/novels/{novel.novel_id}/chapters/visibility",
            json={"start": 3, "end": 3, "isPublic": False},
            headers=_auth_headers(novel_access_scenario.users["owner"]),
        )
        assert unpublish_single.status_code == status.HTTP_200_OK
        assert unpublish_single.json() == {"updatedChapterNums": [3], "isPublic": False}
        test_db.expire_all()
        chapters = test_db.scalars(
            select(Chapter).where(Chapter.novel_id == novel.novel_id).order_by(Chapter.chapter_num)
        ).all()
        assert [(chapter.chapter_num, chapter.chapter_is_public) for chapter in chapters] == [
            (1, True),
            (2, True),
            (3, False),
            (4, True),
        ]

    def test_empty_range_returns_empty_list_for_editor_and_enforces_permissions(
        self, client: TestClient, test_db: Session, novel_access_scenario: DatabaseScenario
    ) -> None:
        public_novel = novel_access_scenario.novels["put"]
        private_novel = novel_access_scenario.novels["prt"]
        viewer_novel = novel_access_scenario.novels["ov"]
        test_db.add(
            Chapter(novel_id=public_novel.novel_id, chapter_num=1, chapter_title="Ch 1", chapter_is_public=True)
        )
        test_db.commit()

        empty = client.post(
            f"/novels/{public_novel.novel_id}/chapters/visibility",
            json={"start": 10, "end": 20, "isPublic": True},
            headers=_auth_headers(novel_access_scenario.users["owner"]),
        )
        assert empty.status_code == status.HTTP_200_OK
        assert empty.json() == {"updatedChapterNums": [], "isPublic": True}

        viewer_denied = client.post(
            f"/novels/{viewer_novel.novel_id}/chapters/visibility",
            json={"isPublic": True},
            headers=_auth_headers(novel_access_scenario.users["other"]),
        )
        assert viewer_denied.status_code == status.HTTP_401_UNAUTHORIZED

        outsider_public = client.post(
            f"/novels/{public_novel.novel_id}/chapters/visibility",
            json={"isPublic": False},
            headers=_auth_headers(novel_access_scenario.users["other"]),
        )
        assert outsider_public.status_code == status.HTTP_401_UNAUTHORIZED

        outsider_private = client.post(
            f"/novels/{private_novel.novel_id}/chapters/visibility",
            json={"isPublic": True},
            headers=_auth_headers(novel_access_scenario.users["other"]),
        )
        assert outsider_private.status_code == status.HTTP_404_NOT_FOUND

        missing = client.post(
            f"/novels/{uuid.uuid4()}/chapters/visibility",
            json={"isPublic": True},
            headers=_auth_headers(novel_access_scenario.users["owner"]),
        )
        assert missing.status_code == status.HTTP_404_NOT_FOUND

    def test_unpublishing_hides_chapters_from_outsiders(
        self, client: TestClient, test_db: Session, novel_access_scenario: DatabaseScenario
    ) -> None:
        novel = novel_access_scenario.novels["put"]
        for num in (1, 2):
            test_db.add(
                Chapter(novel_id=novel.novel_id, chapter_num=num, chapter_title=f"Ch {num}", chapter_is_public=True)
            )
        test_db.commit()

        resp = client.post(
            f"/novels/{novel.novel_id}/chapters/visibility",
            json={"start": 2, "end": 2, "isPublic": False},
            headers=_auth_headers(novel_access_scenario.users["owner"]),
        )
        assert resp.status_code == status.HTTP_200_OK

        outsider_chapters = client.get(
            f"/chapters?novelId={novel.novel_id}",
            headers=_auth_headers(novel_access_scenario.users["other"]),
        )
        assert outsider_chapters.status_code == status.HTTP_200_OK
        assert [chapter["chapterNum"] for chapter in outsider_chapters.json()] == [1]

        owner_chapters = client.get(
            f"/chapters?novelId={novel.novel_id}",
            headers=_auth_headers(novel_access_scenario.users["owner"]),
        )
        assert owner_chapters.status_code == status.HTTP_200_OK
        assert [chapter["chapterNum"] for chapter in owner_chapters.json()] == [1, 2]

    def test_inverted_range_returns_422(self, client: TestClient, novel_access_scenario: DatabaseScenario) -> None:
        novel = novel_access_scenario.novels["put"]
        response = client.post(
            f"/novels/{novel.novel_id}/chapters/visibility",
            json={"start": 5, "end": 2, "isPublic": True},
            headers=_auth_headers(novel_access_scenario.users["owner"]),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
