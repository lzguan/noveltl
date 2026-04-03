"""
Tests for glossary translation job endpoints.

Tests cover:
- Create translation job (POST /glossaries/{id}/translate)
- List translation jobs (GET /glossaries/{id}/translation-jobs)
- Get single translation job (GET /glossaries/{id}/translation-jobs/{job_id})
- Permission enforcement (auth required, outsider gets 404)
- Not-found cases (bad glossary_id, bad job_id)
"""

import uuid
from collections.abc import Generator
from typing import Any, Protocol

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.glossaries.constants import GlossaryRole, TranslationJobStatus
from src.glossaries.dependencies import get_translation_dispatcher
from src.glossaries.models import Glossary, GlossaryContributor, GlossaryEntry, GlossaryTranslationJob
from src.languages.models import Language
from src.main import app
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Contributor, Novel


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...
    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


# ===========================================================================
# Mock Dispatcher
# ===========================================================================


class MockDispatcher:
    """No-op dispatcher that avoids requiring a real Redis connection."""

    async def enqueue(self, job_id: str, translation_job_id: uuid.UUID, model_name: str | None) -> None:
        pass


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def tj_language(test_db: Session) -> Language:
    lang_zh = Language(language_name="Chinese", language_code="zh")
    lang_en = Language(language_name="English", language_code="en")
    test_db.add_all([lang_zh, lang_en])
    test_db.commit()
    return lang_zh


@pytest.fixture
def tj_owner(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="tj_owner", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def tj_editor(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="tj_editor", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def tj_outsider(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="tj_outsider", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def tj_novel(test_db: Session, tj_language: Language, tj_owner: User) -> Novel:
    novel = Novel(
        novel_title="TJ Novel",
        language_code=tj_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=tj_owner.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def tj_glossary(test_db: Session, tj_novel: Novel, tj_owner: User) -> Glossary:
    glossary = Glossary(
        glossary_name="TJ Glossary",
        novel_id=tj_novel.novel_id,
        source_language_code="zh",
        target_language_code="en",
    )
    test_db.add(glossary)
    test_db.commit()
    test_db.add(
        GlossaryContributor(
            glossary_id=glossary.glossary_id,
            user_id=tj_owner.user_id,
            glossary_contributor_role=GlossaryRole.OWNER,
        )
    )
    test_db.commit()
    return glossary


@pytest.fixture
def tj_glossary_with_editor(test_db: Session, tj_glossary: Glossary, tj_editor: User) -> Glossary:
    test_db.add(
        GlossaryContributor(
            glossary_id=tj_glossary.glossary_id,
            user_id=tj_editor.user_id,
            glossary_contributor_role=GlossaryRole.EDITOR,
        )
    )
    test_db.commit()
    return tj_glossary


@pytest.fixture
def tj_entries(test_db: Session, tj_glossary: Glossary) -> list[GlossaryEntry]:
    entries = [
        GlossaryEntry(glossary_id=tj_glossary.glossary_id, source_term="龙", entity_type="MISC"),
        GlossaryEntry(glossary_id=tj_glossary.glossary_id, source_term="李明", entity_type="PER"),
        GlossaryEntry(glossary_id=tj_glossary.glossary_id, source_term="天山", entity_type="LOC"),
    ]
    test_db.add_all(entries)
    test_db.commit()
    return entries


@pytest.fixture
def tj_existing_job(test_db: Session, tj_glossary: Glossary) -> GlossaryTranslationJob:
    job = GlossaryTranslationJob(
        glossary_id=tj_glossary.glossary_id,
        status=TranslationJobStatus.DONE,
        entries_total=3,
        entries_translated=3,
    )
    test_db.add(job)
    test_db.commit()
    return job


@pytest.fixture
def client_with_mock_dispatcher(test_db: Session, client: TestClient) -> Generator[TestClient, None, None]:
    """Override the translation dispatcher dependency with a no-op mock."""
    app.dependency_overrides[get_translation_dispatcher] = lambda: MockDispatcher()
    yield client
    # Clean up only this override; the client fixture handles the rest
    app.dependency_overrides.pop(get_translation_dispatcher, None)


def get_auth_header(client: TestClient, username: str, password: str = "pass") -> dict[str, str]:
    resp = client.post("/token", data={"username": username, "password": password})
    assert resp.status_code == status.HTTP_200_OK
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Create Translation Job Tests
# ===========================================================================


class TestCreateTranslationJob:
    def test_create_translation_job_with_entries(
        self,
        client_with_mock_dispatcher: TestClient,
        tj_owner: User,
        tj_glossary: Glossary,
        tj_entries: list[GlossaryEntry],
    ):
        headers = get_auth_header(client_with_mock_dispatcher, "tj_owner")
        response = client_with_mock_dispatcher.post(
            f"/glossaries/{tj_glossary.glossary_id}/translate",
            json={"model_name": None},
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == TranslationJobStatus.PENDING
        assert data["entries_total"] == len(tj_entries)
        assert data["entries_translated"] == 0
        assert data["glossary_id"] == str(tj_glossary.glossary_id)
        assert "job_id" in data

    def test_create_translation_job_with_model_name(
        self,
        client_with_mock_dispatcher: TestClient,
        tj_owner: User,
        tj_glossary: Glossary,
    ):
        headers = get_auth_header(client_with_mock_dispatcher, "tj_owner")
        response = client_with_mock_dispatcher.post(
            f"/glossaries/{tj_glossary.glossary_id}/translate",
            json={"model_name": "openai"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["job_model_name"] == "openai"

    def test_create_translation_job_empty_glossary(
        self,
        client_with_mock_dispatcher: TestClient,
        tj_owner: User,
        tj_glossary: Glossary,
    ):
        """Glossary with no entries → entries_total = 0."""
        headers = get_auth_header(client_with_mock_dispatcher, "tj_owner")
        response = client_with_mock_dispatcher.post(
            f"/glossaries/{tj_glossary.glossary_id}/translate",
            json={"model_name": None},
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["entries_total"] == 0

    def test_create_translation_job_unauthenticated(
        self,
        client_with_mock_dispatcher: TestClient,
        tj_glossary: Glossary,
    ):
        response = client_with_mock_dispatcher.post(
            f"/glossaries/{tj_glossary.glossary_id}/translate",
            json={"model_name": None},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_translation_job_outsider_gets_404(
        self,
        client_with_mock_dispatcher: TestClient,
        tj_outsider: User,
        tj_glossary: Glossary,
    ):
        headers = get_auth_header(client_with_mock_dispatcher, "tj_outsider")
        response = client_with_mock_dispatcher.post(
            f"/glossaries/{tj_glossary.glossary_id}/translate",
            json={"model_name": None},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_translation_job_bad_glossary_id(
        self,
        client_with_mock_dispatcher: TestClient,
        tj_owner: User,
    ):
        headers = get_auth_header(client_with_mock_dispatcher, "tj_owner")
        bad_id = uuid.uuid4()
        response = client_with_mock_dispatcher.post(
            f"/glossaries/{bad_id}/translate",
            json={"model_name": None},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_translation_job_editor_can_create(
        self,
        client_with_mock_dispatcher: TestClient,
        tj_editor: User,
        tj_glossary_with_editor: Glossary,
    ):
        headers = get_auth_header(client_with_mock_dispatcher, "tj_editor")
        response = client_with_mock_dispatcher.post(
            f"/glossaries/{tj_glossary_with_editor.glossary_id}/translate",
            json={"model_name": None},
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED


# ===========================================================================
# List Translation Jobs Tests
# ===========================================================================


class TestListTranslationJobs:
    def test_list_translation_jobs(
        self,
        client: TestClient,
        tj_owner: User,
        tj_glossary: Glossary,
        tj_existing_job: GlossaryTranslationJob,
    ):
        headers = get_auth_header(client, "tj_owner")
        response = client.get(
            f"/glossaries/{tj_glossary.glossary_id}/translation-jobs",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["job_id"] == str(tj_existing_job.job_id)

    def test_list_translation_jobs_empty(
        self,
        client: TestClient,
        tj_owner: User,
        tj_glossary: Glossary,
    ):
        headers = get_auth_header(client, "tj_owner")
        response = client.get(
            f"/glossaries/{tj_glossary.glossary_id}/translation-jobs",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_translation_jobs_bad_glossary_id(
        self,
        client: TestClient,
        tj_owner: User,
    ):
        headers = get_auth_header(client, "tj_owner")
        bad_id = uuid.uuid4()
        response = client.get(
            f"/glossaries/{bad_id}/translation-jobs",
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_translation_jobs_unauthenticated(
        self,
        client: TestClient,
        tj_glossary: Glossary,
    ):
        response = client.get(f"/glossaries/{tj_glossary.glossary_id}/translation-jobs")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# Get Single Translation Job Tests
# ===========================================================================


class TestGetTranslationJob:
    def test_get_translation_job(
        self,
        client: TestClient,
        tj_owner: User,
        tj_glossary: Glossary,
        tj_existing_job: GlossaryTranslationJob,
    ):
        headers = get_auth_header(client, "tj_owner")
        response = client.get(
            f"/glossaries/{tj_glossary.glossary_id}/translation-jobs/{tj_existing_job.job_id}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["job_id"] == str(tj_existing_job.job_id)
        assert data["glossary_id"] == str(tj_glossary.glossary_id)
        assert data["status"] == TranslationJobStatus.DONE

    def test_get_translation_job_not_found(
        self,
        client: TestClient,
        tj_owner: User,
        tj_glossary: Glossary,
    ):
        headers = get_auth_header(client, "tj_owner")
        bad_job_id = uuid.uuid4()
        response = client.get(
            f"/glossaries/{tj_glossary.glossary_id}/translation-jobs/{bad_job_id}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_translation_job_bad_glossary_id(
        self,
        client: TestClient,
        tj_owner: User,
        tj_existing_job: GlossaryTranslationJob,
    ):
        headers = get_auth_header(client, "tj_owner")
        bad_id = uuid.uuid4()
        response = client.get(
            f"/glossaries/{bad_id}/translation-jobs/{tj_existing_job.job_id}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_translation_job_unauthenticated(
        self,
        client: TestClient,
        tj_glossary: Glossary,
        tj_existing_job: GlossaryTranslationJob,
    ):
        response = client.get(f"/glossaries/{tj_glossary.glossary_id}/translation-jobs/{tj_existing_job.job_id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_translation_job_outsider_gets_404(
        self,
        client: TestClient,
        tj_outsider: User,
        tj_glossary: Glossary,
        tj_existing_job: GlossaryTranslationJob,
    ):
        headers = get_auth_header(client, "tj_outsider")
        response = client.get(
            f"/glossaries/{tj_glossary.glossary_id}/translation-jobs/{tj_existing_job.job_id}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
