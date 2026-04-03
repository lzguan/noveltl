import logging
import uuid
from typing import Any, cast

from sqlalchemy import CursorResult, select, update

from ...glossaries.models import GlossaryEntry
from ...novels.constants import AssociationType, NovelType, Visibility
from ...novels.models import Chapter, Novel, NovelAssociation, Revision, RevisionText
from ..constants import ChapterTranslationStatus, NovelTranslationStatus
from ..models import ChapterTranslationMapping, NovelTranslationJob
from .config import SessionLocal
from .interfaces import ChapterTranslationModel

logger = logging.getLogger(__name__)

translation_model_cache: dict[str, ChapterTranslationModel] = {}


def get_translation_model(model_name: str | None) -> ChapterTranslationModel:
    """
    Retrieve a ChapterTranslationModel instance by name.

    If model_name is None, uses 'openai' as default.
    """
    effective_name = model_name or "openai"
    if effective_name in translation_model_cache:
        return translation_model_cache[effective_name]
    raise ValueError(f"Translation model '{effective_name}' not found in registry.")


async def translate_novel(ctx: dict[str, Any], job_id: str, translation_job_id: uuid.UUID) -> None:
    """
    ARQ worker task to translate an entire novel chapter-by-chapter.

    Follows the autolabels optimistic-locking pattern:
    1. Claim the job by atomically setting status=PROCESSING where status=PENDING
       and job_last_job_id matches.
    2. Fetch source novel metadata and create the target novel.
    3. Fetch glossary entries (if a glossary is attached).
    4. For each chapter mapping, translate the source chapter and write the result.
    5. Set final status to DONE or FAILED.
    """
    base_update = (
        update(NovelTranslationJob)
        .where(NovelTranslationJob.job_id == translation_job_id)
        .where(NovelTranslationJob.job_last_job_id == job_id)
    )

    # --- Validate model ---
    with SessionLocal() as db:
        try:
            q = select(NovelTranslationJob.job_model_name).where(NovelTranslationJob.job_id == translation_job_id)
            model_name = db.execute(q).scalar_one()
        except Exception as e:
            logger.error("Failed to fetch job model name: %s", e)
            raise

    try:
        translation_model = get_translation_model(model_name)
    except ValueError as e:
        with SessionLocal() as db:
            stmt = base_update.values(
                status=NovelTranslationStatus.FAILED,
                job_message=str(e),
            )
            db.execute(stmt)
            db.commit()
        raise

    # --- Claim the job: PENDING -> PROCESSING (optimistic lock) ---
    claim_stmt = base_update.where(NovelTranslationJob.status == NovelTranslationStatus.PENDING).values(
        status=NovelTranslationStatus.PROCESSING
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

    # --- Fetch job metadata and source novel info ---
    with SessionLocal() as db:
        try:
            q = (
                select(
                    NovelTranslationJob.source_novel_id,
                    NovelTranslationJob.target_language_code,
                    NovelTranslationJob.glossary_id,
                    Novel.novel_title,
                    Novel.novel_visibility,
                    Novel.novel_description,
                    Novel.novel_author,
                )
                .select_from(NovelTranslationJob)
                .join(Novel, Novel.novel_id == NovelTranslationJob.source_novel_id)
                .where(NovelTranslationJob.job_id == translation_job_id)
            )
            row = db.execute(q).one()
            source_novel_id: uuid.UUID = row[0]
            target_lang: str = row[1]
            glossary_id: uuid.UUID | None = row[2]
            source_title: str = row[3]
            source_visibility: Visibility = row[4]
            source_description: str | None = row[5]
            source_author: str | None = row[6]
        except Exception as e:
            _fail_job(base_update, f"Failed to fetch job metadata: {e}")
            raise

    # --- Fetch source language code from the source novel ---
    with SessionLocal() as db:
        try:
            q = select(Novel.language_code).where(Novel.novel_id == source_novel_id)
            source_lang: str = db.execute(q).scalar_one()
        except Exception as e:
            _fail_job(base_update, f"Failed to fetch source language: {e}")
            raise

    # --- Create target novel ---
    target_novel_title = f"{source_title} [{target_lang}]"
    with SessionLocal() as db:
        try:
            target_novel = Novel(
                novel_title=target_novel_title,
                novel_description=source_description,
                novel_author=source_author,
                novel_visibility=source_visibility,
                novel_type=NovelType.TRANSLATION,
                language_code=target_lang,
            )
            db.add(target_novel)
            db.flush()
            target_novel_id: uuid.UUID = target_novel.novel_id

            # Create association: source -> target
            association = NovelAssociation(
                source_novel_id=source_novel_id,
                target_novel_id=target_novel_id,
                association_type=AssociationType.TRANSLATION,
            )
            db.add(association)

            # Update job with target_novel_id
            stmt = (
                update(NovelTranslationJob)
                .where(NovelTranslationJob.job_id == translation_job_id)
                .values(target_novel_id=target_novel_id)
            )
            db.execute(stmt)
            db.commit()
        except Exception as e:
            db.rollback()
            _fail_job(base_update, f"Failed to create target novel: {e}")
            raise

    # --- Fetch glossary entries if glossary_id is set ---
    glossary_pairs: list[tuple[str, str]] | None = None
    if glossary_id is not None:
        with SessionLocal() as db:
            try:
                q = (
                    select(
                        GlossaryEntry.source_term,
                        GlossaryEntry.translated_term,
                    )
                    .where(GlossaryEntry.glossary_id == glossary_id)
                    .where(GlossaryEntry.translated_term.is_not(None))
                    .where(GlossaryEntry.translated_term != "")
                    .order_by(GlossaryEntry.source_term)
                )
                rows = db.execute(q).all()
                if rows:
                    glossary_pairs = [(r[0], r[1]) for r in rows]
            except Exception as e:
                logger.warning("Failed to fetch glossary entries, proceeding without: %s", e)

    # --- Fetch chapter mappings ordered by source chapter number ---
    with SessionLocal() as db:
        try:
            q = (
                select(
                    ChapterTranslationMapping.mapping_id,
                    ChapterTranslationMapping.source_chapter_id,
                    Chapter.chapter_num,
                )
                .select_from(ChapterTranslationMapping)
                .join(Chapter, Chapter.chapter_id == ChapterTranslationMapping.source_chapter_id)
                .where(ChapterTranslationMapping.job_id == translation_job_id)
                .order_by(Chapter.chapter_num)
            )
            mappings = db.execute(q).all()
        except Exception as e:
            _fail_job(base_update, f"Failed to fetch chapter mappings: {e}")
            raise

    # --- Translate each chapter ---
    chapters_translated = 0
    chapters_failed = 0
    failure_messages: list[str] = []

    for mapping_id, source_chapter_id, chapter_num in mappings:
        try:
            _translate_chapter(
                translation_model=translation_model,
                mapping_id=mapping_id,
                source_chapter_id=source_chapter_id,
                chapter_num=chapter_num,
                target_novel_id=target_novel_id,
                translation_job_id=translation_job_id,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary_pairs=glossary_pairs,
            )
            chapters_translated += 1

            # Update progress on the job
            with SessionLocal() as db:
                stmt = (
                    update(NovelTranslationJob)
                    .where(NovelTranslationJob.job_id == translation_job_id)
                    .values(chapters_translated=chapters_translated)
                )
                db.execute(stmt)
                db.commit()

        except Exception as e:
            chapters_failed += 1
            msg = f"Chapter {chapter_num}: {e}"
            failure_messages.append(msg)
            logger.exception("Failed to translate chapter %d (mapping %s)", chapter_num, mapping_id)

            # Mark mapping as FAILED
            with SessionLocal() as db:
                stmt = (
                    update(ChapterTranslationMapping)
                    .where(ChapterTranslationMapping.mapping_id == mapping_id)
                    .values(
                        status=ChapterTranslationStatus.FAILED,
                        mapping_message=str(e)[:500],
                    )
                )
                db.execute(stmt)
                db.commit()

    # --- Set final job status ---
    if chapters_failed > 0:
        summary = f"{chapters_failed} chapter(s) failed. " + "; ".join(failure_messages[:5])
        _fail_job(base_update, summary[:1000])
    else:
        with SessionLocal() as db:
            stmt = base_update.values(
                status=NovelTranslationStatus.DONE,
                chapters_translated=chapters_translated,
            )
            db.execute(stmt)
            db.commit()

    logger.info(
        "Translation job %s finished: %d translated, %d failed.",
        translation_job_id,
        chapters_translated,
        chapters_failed,
    )


def _translate_chapter(
    *,
    translation_model: ChapterTranslationModel,
    mapping_id: uuid.UUID,
    source_chapter_id: uuid.UUID,
    chapter_num: int,
    target_novel_id: uuid.UUID,
    translation_job_id: uuid.UUID,
    source_lang: str,
    target_lang: str,
    glossary_pairs: list[tuple[str, str]] | None,
) -> None:
    """
    Translate a single chapter: read source text, call LLM, write target chapter + revision.

    Raises on any failure so the caller can mark the mapping as FAILED.
    """
    # Mark mapping as PROCESSING
    with SessionLocal() as db:
        stmt = (
            update(ChapterTranslationMapping)
            .where(ChapterTranslationMapping.mapping_id == mapping_id)
            .values(status=ChapterTranslationStatus.PROCESSING)
        )
        db.execute(stmt)
        db.commit()

    # Fetch source chapter's latest revision text (highest version)
    with SessionLocal() as db:
        q = (
            select(
                RevisionText.revision_text_content,
                Revision.revision_title,
            )
            .select_from(RevisionText)
            .join(Revision, Revision.revision_id == RevisionText.revision_id)
            .join(Chapter, Chapter.chapter_id == Revision.chapter_id)
            .where(Chapter.chapter_id == source_chapter_id)
            .where(Revision.revision_is_primary.is_(True))
            .order_by(RevisionText.revision_text_version.desc())
            .limit(1)
        )
        row = db.execute(q).one_or_none()
        if row is None:
            raise ValueError(f"No revision text found for source chapter {source_chapter_id}")
        source_text: str = row[0]
        source_title: str | None = row[1]

    # Call the translation model
    translated_text = translation_model.translate(
        source_text=source_text,
        source_lang=source_lang,
        target_lang=target_lang,
        glossary_entries=glossary_pairs,
    )

    # Create target chapter, revision, and revision text
    with SessionLocal() as db:
        target_chapter = Chapter(
            chapter_num=chapter_num,
            novel_id=target_novel_id,
        )
        db.add(target_chapter)
        db.flush()

        target_revision = Revision(
            revision_title=source_title or f"Chapter {chapter_num}",
            revision_is_primary=True,
            revision_is_public=True,
            chapter_id=target_chapter.chapter_id,
        )
        db.add(target_revision)
        db.flush()

        target_revision_text = RevisionText(
            revision_text_content=translated_text,
            revision_text_version=1,
            revision_id=target_revision.revision_id,
        )
        db.add(target_revision_text)
        db.flush()

        # Update mapping with target chapter ID and mark as DONE
        stmt = (
            update(ChapterTranslationMapping)
            .where(ChapterTranslationMapping.mapping_id == mapping_id)
            .values(
                target_chapter_id=target_chapter.chapter_id,
                status=ChapterTranslationStatus.DONE,
            )
        )
        db.execute(stmt)
        db.commit()


def _fail_job(base_update: Any, message: str) -> None:
    """Helper to mark a job as failed."""
    logger.error("Translation job failed: %s", message)
    with SessionLocal() as db:
        stmt = base_update.values(
            status=NovelTranslationStatus.FAILED,
            job_message=message,
        )
        db.execute(stmt)
        db.commit()
