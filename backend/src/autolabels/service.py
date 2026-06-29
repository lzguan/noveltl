"""
Service functions for auto labeling.
"""

import asyncio
import uuid
from collections.abc import Coroutine
from typing import Any
from uuid import uuid4

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from sqlalchemy import and_, exists, func, insert, literal, not_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session, defer

from src.autolabels.params import ModelName

from ..auth.models import User
from ..novels import models as novel_models
from . import models, schemas
from .constants import AutoLabelProgress
from .exceptions import AutoLabelDuplicateException, AutoLabelNotFoundException
from .permissions import auto_label_mod_access_insert, auto_label_mod_access_select
from .utils import AutoLabelDispatcher


def query_auto_label_by_id(db: Session, current_user: User, auto_label_id: uuid.UUID) -> models.AutoLabel:
    """
    Query an autolabel with a specific id from database.

    Args:
        db: Databse to query from.
        current_user: User querying the autolabel.
        autolabel_id: id of autolabel to query.

    Raises:
        AutoLabelNotFoundException: Auto label not found in database.
    """
    q = select(models.AutoLabel).where(models.AutoLabel.auto_label_id == auto_label_id)
    q = auto_label_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        autolabel = result.scalar_one()
    except NoResultFound as e:
        raise AutoLabelNotFoundException from e
    return autolabel


def query_auto_labels(
    db: Session,
    current_user: User,
    novel_id: uuid.UUID,
    chapter_ids: list[uuid.UUID] | None,
    start: int | None,
    end: int | None,
    model_names: list[ModelName] | None,
) -> list[schemas.AutoLabelMeta]:
    """
    Query auto-labels with filtering and return lightweight metadata.

    Args:
        db: Database session.
        current_user: The user requesting the data. Non-admins only see public chapters.
        novel_id: ID of the novel to filter by.
        chapter_ids: Optional list of chapter IDs to filter.
        start: Optional start chapter number (inclusive).
        end: Optional end chapter number (exclusive).
        model_names: Optional names of the auto-label model to filter by.
    """
    q = (
        select(models.AutoLabel)
        .options(defer(models.AutoLabel.auto_label_data))
        .join(
            novel_models.ChapterContent,
            novel_models.ChapterContent.chapter_content_id == models.AutoLabel.chapter_content_id,
        )
        .join(novel_models.Chapter, novel_models.Chapter.chapter_id == novel_models.ChapterContent.chapter_id)
        .join(novel_models.Novel, novel_models.Novel.novel_id == novel_models.Chapter.novel_id)
        .where(novel_models.Novel.novel_id == novel_id)
    )
    if chapter_ids is not None and len(chapter_ids) > 0:
        q = q.where(novel_models.Chapter.chapter_id.in_(chapter_ids))
    if start is not None:
        q = q.where(novel_models.Chapter.chapter_num >= start)
    if end is not None:
        q = q.where(novel_models.Chapter.chapter_num < end)
    if model_names is not None and len(model_names) > 0:
        q = q.where(models.AutoLabel.auto_label_model_name.in_(model_names))
    q = auto_label_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()
    return [schemas.AutoLabelMeta.model_validate(row) for row in result_rows]


async def insert_auto_labels(
    db: Session, current_user: User, dispatcher: AutoLabelDispatcher, request: schemas.CreateAutoLabels
) -> list[schemas.AutoLabelMeta]:
    """
    Insert new autolabels that correspond to the request, queue the corresponding tasks, and return a list of autolabels that were newly inserted.

    Args:
        db: Database to insert into.
        current_user: User performing the action.
        request: Request metadata.

    Raises:
        AutoLabelDuplicateException: If insertion violates a unique constraint. Will most likely occur when there is a race condition.

    Notes:
        This function ignores all chapter content IDs that do not exist and chapters that the user has insufficient permissions for.
    """
    columns: list[Any] = [
        models.AutoLabel.auto_label_model_name,
        models.AutoLabel.auto_label_model_params,
        models.AutoLabel.auto_label_status,
        models.AutoLabel.auto_label_message,
        models.AutoLabel.chapter_content_id,
    ]
    q = (
        select(
            literal(request.params.model_name),
            literal(request.params.model_dump(mode="json"), type_=JSONB),
            literal(AutoLabelProgress.PENDING),
            literal("Waiting to be queued."),
            novel_models.ChapterContent.chapter_content_id,
        )
        .select_from(novel_models.ChapterContent)
        .join(novel_models.Chapter, novel_models.Chapter.chapter_id == novel_models.ChapterContent.chapter_id)
        .join(novel_models.Novel, novel_models.Novel.novel_id == novel_models.Chapter.novel_id)
        .where(
            novel_models.ChapterContent.chapter_content_version
            == select(func.max(novel_models.ChapterContent.chapter_content_version))
            .where(novel_models.ChapterContent.chapter_id == novel_models.Chapter.chapter_id)
            .correlate(novel_models.Chapter)
            .scalar_subquery()
        )
    )
    if request.chapter_ids:
        q = q.where(novel_models.Chapter.chapter_id.in_(request.chapter_ids))
    if request.start is not None:
        q = q.where(novel_models.Chapter.chapter_num >= request.start)
    if request.end is not None:
        q = q.where(novel_models.Chapter.chapter_num < request.end)
    if request.is_public is not None:
        q = q.where(novel_models.Chapter.chapter_is_public == request.is_public)
    q = auto_label_mod_access_insert(q, current_user)
    q = q.where(
        not_(
            exists(
                select(models.AutoLabel).where(
                    and_(
                        models.AutoLabel.chapter_content_id == novel_models.ChapterContent.chapter_content_id,
                        models.AutoLabel.auto_label_model_name == request.params.model_name,
                        models.AutoLabel.auto_label_model_params == request.params.model_dump(mode="json"),
                    )
                )
            )
        )
    )
    stmt = insert(models.AutoLabel).from_select(columns, q).returning(models.AutoLabel)
    try:
        result = db.execute(stmt)
        result_rows = result.scalars().all()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.UNIQUE_VIOLATION:
                raise AutoLabelDuplicateException from e
        raise
    except Exception:
        db.rollback()
        raise

    tasks: list[Coroutine[Any, Any, None]] = []
    for autolabel in result_rows:
        job_id = str(uuid4())
        autolabel.auto_label_last_job_id = job_id
        tasks.append(dispatcher.enqueue(job_id, autolabel.auto_label_id, request.params))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    ret = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(ret):
        autolabel = result_rows[i]
        if result is None:
            autolabel.auto_label_message = "Job queued."
        else:
            autolabel.auto_label_message = "Job failed to queue."
            autolabel.auto_label_status = AutoLabelProgress.FAILED
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return [schemas.AutoLabelMeta.model_validate(autolabel) for autolabel in result_rows]


def regenerate_auto_labels():
    pass
