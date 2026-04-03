"""
Service functions for novel translation jobs.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, insert, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from ..auth.models import User
from ..exceptions import UnknownError
from ..novels.exceptions import NovelNotFoundException
from ..novels.models import Chapter
from . import models, schemas
from .constants import ChapterTranslationStatus, NovelTranslationStatus
from .exceptions import NovelTranslationJobNotFoundException
from .permissions import (
    novel_translation_job_mod_access_insert,
    novel_translation_job_mod_access_select,
)


def insert_translation_job(
    db: Session,
    current_user: User,
    create_data: schemas.CreateNovelTranslationJob,
) -> models.NovelTranslationJob:
    """
    Create a new novel translation job.

    Counts chapters in the source novel and creates a ChapterTranslationMapping
    for each. Does not create the target novel — the worker does that.

    Raises:
        NovelNotFoundException: Source novel not found or user lacks editor/owner access.
        UnknownError: Unexpected error.
    """
    source_novel_id = create_data.source_novel_id

    # Count chapters for the source novel
    count_result = db.execute(select(func.count()).select_from(Chapter).where(Chapter.novel_id == source_novel_id))
    chapters_total: int = count_result.scalar_one()

    # Build the job row using insert-from-select for atomic permission check
    row_data = [
        ("source_novel_id", source_novel_id),
        ("target_novel_id", None),
        ("glossary_id", create_data.glossary_id),
        ("status", NovelTranslationStatus.PENDING),
        ("job_model_name", create_data.model_name),
        ("job_last_job_id", None),
        ("job_message", None),
        ("chapters_translated", 0),
        ("chapters_total", chapters_total),
        ("target_language_code", create_data.target_language_code),
    ]
    cols = [k for k, _ in row_data]

    from sqlalchemy import literal

    vals = select(*[literal(v) for _, v in row_data])
    vals = novel_translation_job_mod_access_insert(vals, current_user, source_novel_id)

    stmt = insert(models.NovelTranslationJob).from_select(cols, vals).returning(models.NovelTranslationJob)
    try:
        result = db.execute(stmt)
        job = result.scalar_one()
    except NoResultFound as e:
        db.rollback()
        raise NovelNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e

    # Fetch chapters to create per-chapter mappings
    chapters_q = select(Chapter.chapter_id).where(Chapter.novel_id == source_novel_id)
    chapter_ids = db.execute(chapters_q).scalars().all()

    try:
        for chapter_id in chapter_ids:
            mapping_stmt = insert(models.ChapterTranslationMapping).values(
                job_id=job.job_id,
                source_chapter_id=chapter_id,
                target_chapter_id=None,
                status=ChapterTranslationStatus.PENDING,
                mapping_message=None,
            )
            db.execute(mapping_stmt)
        db.commit()
    except Exception as e:
        db.rollback()
        raise UnknownError from e

    return job


def query_translation_jobs(
    db: Session,
    current_user: User,
    source_novel_id: uuid.UUID,
) -> Sequence[models.NovelTranslationJob]:
    """
    List all translation jobs for a source novel that the user has access to.

    Raises:
        NovelNotFoundException: Source novel not found or user lacks contributor access.
    """
    q = (
        select(models.NovelTranslationJob)
        .where(models.NovelTranslationJob.source_novel_id == source_novel_id)
        .order_by(models.NovelTranslationJob.created_at.desc())
    )
    q = novel_translation_job_mod_access_select(q, current_user)
    result = db.execute(q)
    return result.scalars().all()


def query_translation_job(
    db: Session,
    current_user: User,
    job_id: uuid.UUID,
) -> models.NovelTranslationJob:
    """
    Get a single translation job by id, including chapter mappings.

    Raises:
        NovelTranslationJobNotFoundException: Job not found or user lacks access.
    """
    q = select(models.NovelTranslationJob).where(models.NovelTranslationJob.job_id == job_id)
    q = novel_translation_job_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        return result.scalar_one()
    except NoResultFound as e:
        raise NovelTranslationJobNotFoundException from e
