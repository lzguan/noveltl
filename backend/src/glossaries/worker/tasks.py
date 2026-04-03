import logging
import uuid
from typing import Any, cast

from sqlalchemy import CursorResult, select, update

from ..constants import TranslationJobStatus
from ..models import Glossary, GlossaryEntry, GlossaryTranslationJob
from .config import SessionLocal
from .interfaces import TranslationModel

logger = logging.getLogger(__name__)

translation_model_cache: dict[str, TranslationModel] = {}


def get_translation_model(model_name: str | None) -> TranslationModel:
    """
    Retrieve a TranslationModel instance by name.

    If model_name is None, uses 'openai' as default.
    Caches model instances to avoid re-initialization.
    """
    effective_name = model_name or "openai"
    if effective_name in translation_model_cache:
        return translation_model_cache[effective_name]
    raise ValueError(f"Translation model '{effective_name}' not found in registry.")


async def glossary_translate(
    ctx: dict[str, Any], job_id: str, translation_job_id: uuid.UUID, model_name: str | None
) -> None:
    """
    Worker task to translate glossary entries via an LLM.

    Follows the autolabels optimistic-locking pattern:
    1. Claim the job by atomically setting status=PROCESSING where status=PENDING and job_last_job_id matches.
    2. Fetch all glossary entries for the glossary associated with this job.
    3. Translate entries in batches using the TranslationModel.
    4. Write translated_term back to each entry and update progress.
    5. Set status=DONE on success, status=FAILED on error.
    """
    base_update = (
        update(GlossaryTranslationJob)
        .where(GlossaryTranslationJob.job_id == translation_job_id)
        .where(GlossaryTranslationJob.job_last_job_id == job_id)
    )

    # Validate model
    try:
        translation_model = get_translation_model(model_name)
    except ValueError as e:
        with SessionLocal() as db:
            stmt = base_update.values(
                status=TranslationJobStatus.FAILED,
                job_message=str(e),
            )
            db.execute(stmt)
            db.commit()
        raise

    # Claim the job: PENDING -> PROCESSING (optimistic lock)
    claim_stmt = base_update.where(GlossaryTranslationJob.status == TranslationJobStatus.PENDING).values(
        status=TranslationJobStatus.PROCESSING
    )
    with SessionLocal() as db:
        try:
            res = db.execute(claim_stmt)
            cursor_res = cast(CursorResult[Any], res)
            if cursor_res.rowcount == 0:
                db.rollback()
                return  # Already claimed or not pending
            db.commit()
        except Exception as e:
            db.rollback()
            raise e

    # Fetch glossary_id and language codes via the translation job
    with SessionLocal() as db:
        try:
            q = (
                select(
                    GlossaryTranslationJob.glossary_id,
                    Glossary.source_language_code,
                    Glossary.target_language_code,
                )
                .select_from(GlossaryTranslationJob)
                .join(Glossary, Glossary.glossary_id == GlossaryTranslationJob.glossary_id)
                .where(GlossaryTranslationJob.job_id == translation_job_id)
            )
            row = db.execute(q).one()
            glossary_id: uuid.UUID = row[0]
            source_lang: str = row[1]
            target_lang: str = row[2]
        except Exception as e:
            _fail_job(base_update, f"Failed to fetch job metadata: {e}")
            raise

    # Fetch entries to translate
    with SessionLocal() as db:
        try:
            q_entries = (
                select(GlossaryEntry.glossary_entry_id, GlossaryEntry.source_term)
                .where(GlossaryEntry.glossary_id == glossary_id)
                .order_by(GlossaryEntry.source_term)
            )
            entries = db.execute(q_entries).all()
        except Exception as e:
            _fail_job(base_update, f"Failed to fetch glossary entries: {e}")
            raise

    if not entries:
        with SessionLocal() as db:
            stmt = base_update.values(
                status=TranslationJobStatus.DONE,
                job_message="No entries to translate.",
                entries_translated=0,
            )
            db.execute(stmt)
            db.commit()
        return

    entry_ids = [row[0] for row in entries]
    source_terms = [row[1] for row in entries]

    # Translate in batches using the model's own batching
    try:
        translated_terms = translation_model.translate(source_terms, source_lang, target_lang)
    except Exception as e:
        _fail_job(base_update, f"Translation failed: {e}")
        raise

    # Write back translated terms in chunks to show progress
    batch_size = 50
    entries_translated = 0
    try:
        for i in range(0, len(entry_ids), batch_size):
            batch_ids = entry_ids[i : i + batch_size]
            batch_translations = translated_terms[i : i + batch_size]

            with SessionLocal() as db:
                for entry_id, translated_term in zip(batch_ids, batch_translations, strict=True):
                    stmt = (
                        update(GlossaryEntry)
                        .where(GlossaryEntry.glossary_entry_id == entry_id)
                        .values(translated_term=translated_term)
                    )
                    db.execute(stmt)
                entries_translated += len(batch_ids)

                # Update progress
                progress_stmt = base_update.values(entries_translated=entries_translated)
                db.execute(progress_stmt)
                db.commit()
    except Exception as e:
        _fail_job(base_update, f"Failed to write translations: {e}")
        raise

    # Mark as done
    with SessionLocal() as db:
        stmt = base_update.values(
            status=TranslationJobStatus.DONE,
            entries_translated=entries_translated,
        )
        db.execute(stmt)
        db.commit()

    logger.info("Translation job %s completed: %d entries translated.", translation_job_id, entries_translated)


def _fail_job(base_update: Any, message: str) -> None:
    """Helper to mark a job as failed."""
    logger.error("Translation job failed: %s", message)
    with SessionLocal() as db:
        stmt = base_update.values(
            status=TranslationJobStatus.FAILED,
            job_message=message,
        )
        db.execute(stmt)
        db.commit()
