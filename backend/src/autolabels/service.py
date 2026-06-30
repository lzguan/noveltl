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
from sqlalchemy import exists, func, insert, literal, select
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session, defer

from ..auth.models import User
from ..novels import models as novel_models
from ..novels.permissions import novel_mod_access_select
from . import models, schemas
from .constants import AutoLabelProgress
from .exceptions import AutoLabelDuplicateException, AutoLabelNotFoundException
from .permissions import auto_label_mod_access_insert, auto_label_mod_access_select
from .utils import AutoLabelDispatcher


def query_auto_label_by_id(db: Session, current_user: User, auto_label_id: uuid.UUID) -> models.AutoLabel:
    """
    Query an autolabel with a specific id from database.

    Args:
        db: Database to query from.
        current_user: User querying the autolabel.
        auto_label_id: id of autolabel to query.

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


def query_auto_label_runs(
    db: Session,
    current_user: User,
    novel_id: uuid.UUID,
    mine: bool = False,
) -> list[schemas.AutoLabelRun]:
    """
    Query autolabel runs for a novel.

    Args:
        db: Database session.
        current_user: User requesting the data.
        novel_id: ID of the novel to filter by.
        mine: If True, only return runs triggered by the current user.
    """
    q = select(models.AutoLabelRun).where(models.AutoLabelRun.novel_id == novel_id)
    if mine:
        q = q.where(models.AutoLabelRun.triggered_by == current_user.user_id)
    # Verify the user has access to the novel.
    subq = select(1).select_from(novel_models.Novel).where(novel_models.Novel.novel_id == novel_id)
    subq = novel_mod_access_select(subq, current_user)
    q = q.where(exists(subq))
    result = db.execute(q)
    rows = result.scalars().all()
    return [schemas.AutoLabelRun.model_validate(row) for row in rows]


def query_auto_labels_by_run(
    db: Session,
    current_user: User,
    run_id: uuid.UUID,
    start: int | None = None,
    end: int | None = None,
) -> list[schemas.AutoLabelMeta]:
    """
    Query autolabels belonging to a specific run.

    Args:
        db: Database session.
        current_user: User requesting the data.
        run_id: ID of the run to query autolabels for.
        start: Optional start chapter number (inclusive).
        end: Optional end chapter number (exclusive).
    """
    q = (
        select(models.AutoLabel)
        .options(defer(models.AutoLabel.auto_label_data))
        .where(models.AutoLabel.run_id == run_id)
    )
    if start is not None or end is not None:
        q = q.join(
            novel_models.ChapterContent,
            novel_models.ChapterContent.chapter_content_id == models.AutoLabel.chapter_content_id,
        ).join(novel_models.Chapter, novel_models.Chapter.chapter_id == novel_models.ChapterContent.chapter_id)
        if start is not None:
            q = q.where(novel_models.Chapter.chapter_num >= start)
        if end is not None:
            q = q.where(novel_models.Chapter.chapter_num < end)
    q = auto_label_mod_access_select(q, current_user)
    result = db.execute(q)
    rows = result.scalars().all()
    return [schemas.AutoLabelMeta.model_validate(row) for row in rows]


async def insert_auto_labels(
    db: Session,
    current_user: User,
    dispatcher: AutoLabelDispatcher,
    request: schemas.CreateAutoLabels,
) -> schemas.CreateAutoLabelsResponse:
    """
    Create a new autolabel run and insert autolabels for matching chapters.

    Args:
        db: Database to insert into.
        current_user: User performing the action.
        dispatcher: Queue dispatcher for worker tasks.
        request: Request specifying novel, model params, and chapter filters.

    Raises:
        AutoLabelDuplicateException: If insertion violates the unique constraint.

    Notes:
        This function ignores chapters the user has insufficient permissions for
        and chapters whose latest content already has an autolabel for this run.
    """
    model_name = request.params.model_name
    model_params_dump = request.params.model_dump(mode="json")

    # 1. Create the run.
    run = models.AutoLabelRun(
        novel_id=request.novel_id,
        triggered_by=current_user.user_id,
        model_name=model_name,
        model_params=model_params_dump,
    )
    db.add(run)
    # Flush to get the server-generated run_id before we insert autolabels.
    db.flush()

    # 2. Insert autolabels for matching chapter contents.
    columns = [
        models.AutoLabel.auto_label_status,
        models.AutoLabel.auto_label_message,
        models.AutoLabel.chapter_content_id,
        models.AutoLabel.run_id,
    ]
    q = (
        select(
            literal(AutoLabelProgress.PENDING),
            literal("Waiting to be queued."),
            novel_models.ChapterContent.chapter_content_id,
            literal(run.run_id),
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

    # 3. Dispatch worker tasks.
    tasks: list[Coroutine[Any, Any, None]] = []
    for autolabel in result_rows:
        job_id = str(uuid4())
        autolabel.auto_label_last_job_id = job_id
        tasks.append(dispatcher.enqueue(job_id, autolabel.auto_label_id))
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

    # 4. Build response.
    run_schema = schemas.AutoLabelRun.model_validate(run)
    autolabel_schemas = [schemas.AutoLabelMeta.model_validate(al) for al in result_rows]
    return schemas.CreateAutoLabelsResponse(run=run_schema, autolabels=autolabel_schemas)


def regenerate_auto_labels():
    pass
