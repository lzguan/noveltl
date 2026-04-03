"""
Tests for the glossary_translate worker task.

Tests cover:
- Happy path: entries get translated_term, job status=DONE
- Optimistic lock: wrong job_id string → no-op (job stays PENDING)
- Already claimed: job status=PROCESSING before call → no-op
- Empty entries: no entries → job status=DONE, message="No entries to translate."
- Model not found: unknown model_name → job status=FAILED
- Partial failure: model that raises on translate() → job status=FAILED with message
"""

import uuid
from collections.abc import Generator
from typing import Any, Protocol

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.auth.constants import UserType
from src.auth.models import User
from src.glossaries.constants import GlossaryRole, TranslationJobStatus
from src.glossaries.models import Glossary, GlossaryContributor, GlossaryEntry, GlossaryTranslationJob
from src.glossaries.worker import tasks as worker_tasks
from src.glossaries.worker.tasks import glossary_translate, translation_model_cache
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Contributor, Novel


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...
    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


# ===========================================================================
# Mock Translation Models
# ===========================================================================


class MockTranslationModel:
    """Returns translated terms by prepending 'translated_' to each source term."""

    def translate(self, source_terms: list[str], source_lang: str, target_lang: str) -> list[str]:
        return [f"translated_{t}" for t in source_terms]


class FailingTranslationModel:
    """Raises an exception on translate() to simulate a model failure."""

    def translate(self, source_terms: list[str], source_lang: str, target_lang: str) -> list[str]:
        raise RuntimeError("Model inference error")


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def patch_session_local(test_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace SessionLocal in the worker module with one pointing at the test DB.
    This is needed because the worker task creates its own sessions independently
    of FastAPI's dependency injection.
    """
    monkeypatch.setattr(worker_tasks, "SessionLocal", sessionmaker(create_engine(test_url)))


@pytest.fixture(autouse=True)
def register_mock_model() -> Generator[None, None, None]:
    """Register the mock model in the translation_model_cache and clean up after."""
    translation_model_cache["mock"] = MockTranslationModel()
    translation_model_cache["failing"] = FailingTranslationModel()
    yield
    translation_model_cache.pop("mock", None)
    translation_model_cache.pop("failing", None)


@pytest.fixture
def w_language(test_db: Session) -> Language:
    lang_zh = Language(language_name="Chinese", language_code="zh")
    lang_en = Language(language_name="English", language_code="en")
    test_db.add_all([lang_zh, lang_en])
    test_db.commit()
    return lang_zh


@pytest.fixture
def w_owner(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="w_owner", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def w_novel(test_db: Session, w_language: Language, w_owner: User) -> Novel:
    novel = Novel(
        novel_title="Worker Novel",
        language_code=w_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=w_owner.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def w_glossary(test_db: Session, w_novel: Novel, w_owner: User) -> Glossary:
    glossary = Glossary(
        glossary_name="Worker Glossary",
        novel_id=w_novel.novel_id,
        source_language_code="zh",
        target_language_code="en",
    )
    test_db.add(glossary)
    test_db.commit()
    test_db.add(
        GlossaryContributor(
            glossary_id=glossary.glossary_id,
            user_id=w_owner.user_id,
            glossary_contributor_role=GlossaryRole.OWNER,
        )
    )
    test_db.commit()
    return glossary


@pytest.fixture
def w_entries(test_db: Session, w_glossary: Glossary) -> list[GlossaryEntry]:
    entries = [
        GlossaryEntry(glossary_id=w_glossary.glossary_id, source_term="龙", entity_type="MISC"),
        GlossaryEntry(glossary_id=w_glossary.glossary_id, source_term="李明", entity_type="PER"),
    ]
    test_db.add_all(entries)
    test_db.commit()
    return entries


def make_pending_job(test_db: Session, glossary: Glossary, entries_total: int = 0) -> GlossaryTranslationJob:
    """Create a PENDING translation job, with job_last_job_id set to its own job_id string (optimistic lock)."""
    job = GlossaryTranslationJob(
        glossary_id=glossary.glossary_id,
        status=TranslationJobStatus.PENDING,
        entries_total=entries_total,
        entries_translated=0,
    )
    test_db.add(job)
    test_db.commit()
    # Set job_last_job_id to the job_id string (same as what the dispatcher would pass)
    job.job_last_job_id = job.job_id
    test_db.commit()
    return job


def refresh_job(test_db: Session, job_id: uuid.UUID) -> GlossaryTranslationJob:
    """Re-fetch the job from the DB to get the latest state committed by the worker."""
    # Expire all cached objects so the next query hits the DB
    test_db.expire_all()
    result = test_db.execute(select(GlossaryTranslationJob).where(GlossaryTranslationJob.job_id == job_id))
    return result.scalar_one()


def refresh_entry(test_db: Session, entry_id: uuid.UUID) -> GlossaryEntry:
    """Re-fetch the entry from the DB to get the latest state committed by the worker."""
    test_db.expire_all()
    result = test_db.execute(select(GlossaryEntry).where(GlossaryEntry.glossary_entry_id == entry_id))
    return result.scalar_one()


# ===========================================================================
# Worker Task Tests
# ===========================================================================


class TestGlossaryTranslateWorker:
    async def test_happy_path(
        self,
        test_db: Session,
        w_glossary: Glossary,
        w_entries: list[GlossaryEntry],
    ):
        """Entries get translated_term; job status = DONE."""
        job = make_pending_job(test_db, w_glossary, entries_total=len(w_entries))
        ctx: dict[str, Any] = {}

        await glossary_translate(ctx, str(job.job_id), job.job_id, "mock")

        final_job = refresh_job(test_db, job.job_id)
        assert final_job.status == TranslationJobStatus.DONE
        assert final_job.entries_translated == len(w_entries)

        for entry in w_entries:
            updated = refresh_entry(test_db, entry.glossary_entry_id)
            assert updated.translated_term == f"translated_{entry.source_term}"

    async def test_optimistic_lock_wrong_job_id(
        self,
        test_db: Session,
        w_glossary: Glossary,
    ):
        """
        If job_last_job_id doesn't match job_id string, the claim step returns
        0 rows and the task is a no-op — job stays PENDING.
        """
        job = make_pending_job(test_db, w_glossary)
        wrong_job_id_str = str(uuid.uuid4())
        ctx: dict[str, Any] = {}

        await glossary_translate(ctx, wrong_job_id_str, job.job_id, "mock")

        final_job = refresh_job(test_db, job.job_id)
        assert final_job.status == TranslationJobStatus.PENDING

    async def test_already_claimed_is_no_op(
        self,
        test_db: Session,
        w_glossary: Glossary,
    ):
        """If the job is already PROCESSING, the claim step finds 0 rows → no-op."""
        job = make_pending_job(test_db, w_glossary)
        # Manually set status to PROCESSING to simulate another worker claiming it
        job.status = TranslationJobStatus.PROCESSING
        test_db.commit()
        ctx: dict[str, Any] = {}

        await glossary_translate(ctx, str(job.job_id), job.job_id, "mock")

        final_job = refresh_job(test_db, job.job_id)
        # The task should not have changed the status
        assert final_job.status == TranslationJobStatus.PROCESSING

    async def test_empty_entries(
        self,
        test_db: Session,
        w_glossary: Glossary,
    ):
        """Glossary with no entries → job status=DONE with 'No entries to translate.' message."""
        job = make_pending_job(test_db, w_glossary, entries_total=0)
        ctx: dict[str, Any] = {}

        await glossary_translate(ctx, str(job.job_id), job.job_id, "mock")

        final_job = refresh_job(test_db, job.job_id)
        assert final_job.status == TranslationJobStatus.DONE
        assert final_job.job_message == "No entries to translate."
        assert final_job.entries_translated == 0

    async def test_model_not_found(
        self,
        test_db: Session,
        w_glossary: Glossary,
    ):
        """Unknown model_name → job status=FAILED."""
        job = make_pending_job(test_db, w_glossary)
        ctx: dict[str, Any] = {}

        with pytest.raises(ValueError):
            await glossary_translate(ctx, str(job.job_id), job.job_id, "nonexistent_model")

        final_job = refresh_job(test_db, job.job_id)
        assert final_job.status == TranslationJobStatus.FAILED

    async def test_model_translate_raises(
        self,
        test_db: Session,
        w_glossary: Glossary,
        w_entries: list[GlossaryEntry],
    ):
        """If the model raises during translate(), job status=FAILED with message."""
        job = make_pending_job(test_db, w_glossary, entries_total=len(w_entries))
        ctx: dict[str, Any] = {}

        with pytest.raises(RuntimeError):
            await glossary_translate(ctx, str(job.job_id), job.job_id, "failing")

        final_job = refresh_job(test_db, job.job_id)
        assert final_job.status == TranslationJobStatus.FAILED
        assert final_job.job_message is not None
        assert "Translation failed" in final_job.job_message
