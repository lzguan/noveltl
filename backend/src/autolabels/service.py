"""
Service functions for auto labeling.

Todo: Rewrite to use more raw sql. This seems like a huge pain in the ass so I am putting this off indefinitely.
"""

import asyncio
from collections.abc import Coroutine
from uuid import uuid4

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from sqlalchemy import and_, exists, insert, literal, not_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session, defer

from ..auth.constants import UserType
from ..auth.models import User
from ..exceptions import InsufficientPermissionsException, UnknownError
from ..novels import models as novel_models
from ..novels.permissions import raw_chapter_revision_mod_access_select
from . import models, schemas
from .constants import AutoLabelProgress
from .exceptions import AutoLabelDuplicateException, AutoLabelNotFoundException
from .utils import AutoLabelDispatcher


def query_auto_label_by_id(db : Session, current_user : User, auto_label_id : int) -> models.AutoLabel:
    """
    Query an autolabel with a specific id from database.

    Args:
        db: Databse to query from.
        current_user: User querying the autolabel.
        autolabel_id: id of autolabel to query.

    Raises:
        AutoLabelNotFoundException: Auto label not found in database.
        InsufficientPermissionsException: User does not have sufficient permissions to view this autolabel.
    """
    q = select(
        models.AutoLabel, novel_models.RawChapterRevision.raw_chapter_revision_is_public
    ).join(
        novel_models.RawChapterRevision,
        novel_models.RawChapterRevision.raw_chapter_revision_id == models.AutoLabel.raw_chapter_revision_id
    ).where(
        models.AutoLabel.auto_label_id == auto_label_id
    )
    try:
        result = db.execute(q)
        a, p = result.one()
        auto_label : models.AutoLabel = a
        is_public : bool = p
    except NoResultFound as e:
        raise AutoLabelNotFoundException from e
    if current_user.user_type != UserType.ADMIN and not is_public:
        raise InsufficientPermissionsException
    return auto_label

def query_auto_labels(
        db : Session,
        current_user : User,
        novel_id : int,
        raw_chapter_ids : list[int] | None,
        raw_chapter_revision_ids : list[int] | None,
        start : int | None,
        end : int | None,
        model_names : list[str] | None,
    ) -> list[schemas.AutoLabelMeta]:
    """
    Query auto-labels with filtering and return lightweight metadata. Return format is a dictionary of the form `raw_chapter_revision_id : AutoLabelMeta`.

    Args:
        db: Database session.
        current_user: The user requesting the data. Non-admins only see public revisions.
        novel_id: ID of the novel to filter by.
        raw_chapter_ids: Optional list of chapter IDs to filter.
        raw_chapter_revision_ids: Optional list of revision IDs to filter.
        start: Optional start chapter number (inclusive).
        end: Optional end chapter number (exclusive).
        model_names: Optional names of the auto-label model to filter by.
    """
    q = select(
        models.AutoLabel
    ).options(
        defer(models.AutoLabel.auto_label_data)
    ).join(
        novel_models.RawChapterRevision,
        novel_models.RawChapterRevision.raw_chapter_revision_id == models.AutoLabel.raw_chapter_revision_id,
    ).join(
        novel_models.RawChapter,
        novel_models.RawChapter.raw_chapter_id == novel_models.RawChapterRevision.raw_chapter_id
    ).join(
        novel_models.Novel,
        novel_models.Novel.novel_id == novel_models.RawChapter.novel_id
    ).where(
        novel_models.RawChapterRevision.raw_chapter_revision_is_final.is_(True)
    ).where(novel_models.Novel.novel_id == novel_id)
    if raw_chapter_ids is not None and len(raw_chapter_ids) > 0:
        q = q.where(novel_models.RawChapter.raw_chapter_id.in_(raw_chapter_ids))
    if raw_chapter_revision_ids is not None and len(raw_chapter_revision_ids) > 0:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_id.in_(raw_chapter_revision_ids))
    if start is not None:
        q = q.where(novel_models.RawChapter.raw_chapter_num >= start)
    if end is not None:
        q = q.where(novel_models.RawChapter.raw_chapter_num < end)
    if model_names is not None and len(model_names) > 0:
        q = q.where(models.AutoLabel.auto_label_model_name.in_(model_names))
    q = raw_chapter_revision_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()
    return [schemas.AutoLabelMeta.model_validate(row) for row in result_rows]

async def insert_auto_labels(db : Session, current_user : User, dispatcher : AutoLabelDispatcher, request : schemas.CreateAutoLabels) -> list[schemas.AutoLabelMeta]:
    """
    Insert new autolabels that correspond to the request, queue the corresponding tasks, and return a list of autolabels that were newly inserted.

    Args:
        db: Database to insert into.
        current_user: User performing the action.
        request: Request metadata.

    Raises:
        AutoLabelDuplicateException: If insertion violates a unique constraint. Will most likely occur when there is a race condition.

    Notes:
        This function ignores all revision IDs that do not exist, revisions that are not final, and revisions that the user has insufficient permissions for.
    """
    columns = [
        models.AutoLabel.auto_label_model_name,
        models.AutoLabel.auto_label_model_params,
        models.AutoLabel.auto_label_status,
        models.AutoLabel.auto_label_message,
        models.AutoLabel.raw_chapter_revision_id
    ]
    q = select(
        literal(request.auto_label_model_name),
        literal(request.auto_label_model_params, type_=JSONB),
        literal(AutoLabelProgress.PENDING),
        literal("Waiting to be queued."),
        novel_models.RawChapterRevision.raw_chapter_revision_id
    ).select_from(
        novel_models.RawChapterRevision
    ).where(
        novel_models.RawChapterRevision.raw_chapter_revision_is_final.is_(True)
    ).join(
        novel_models.RawChapter,
        novel_models.RawChapter.raw_chapter_id == novel_models.RawChapterRevision.raw_chapter_id
    ).join(
        novel_models.Novel,
        novel_models.Novel.novel_id == novel_models.RawChapter.novel_id
    )
    if request.raw_chapter_ids:
        q = q.where(novel_models.RawChapter.raw_chapter_id.in_(request.raw_chapter_ids))
    if request.raw_chapter_revision_ids:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_id.in_(request.raw_chapter_revision_ids))
    if request.start is not None:
        q = q.where(novel_models.RawChapter.raw_chapter_num >= request.start)
    if request.end is not None:
        q = q.where(novel_models.RawChapter.raw_chapter_num < request.end)
    if request.is_primary is not None:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_is_primary == request.is_primary)
    if request.is_public is not None:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_is_public == request.is_public)
    q = raw_chapter_revision_mod_access_select(q, current_user)
    q = q.where(not_(exists(select(models.AutoLabel).where(and_(
        models.AutoLabel.raw_chapter_revision_id == novel_models.RawChapterRevision.raw_chapter_revision_id,
        models.AutoLabel.auto_label_model_name == request.auto_label_model_name,
        models.AutoLabel.auto_label_model_params == request.auto_label_model_params
    )))))
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
        raise UnknownError from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e

    tasks : list[Coroutine] = []
    for autolabel in result_rows:
        job_id = str(uuid4())
        autolabel.auto_label_last_job_id = job_id
        tasks.append(
            dispatcher.enqueue(
                job_id,
                autolabel.auto_label_id,
                request.auto_label_model_name,
                request.auto_label_model_params
            )
        )
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise UnknownError from e

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
    except Exception as e:
        raise UnknownError from e
    return [schemas.AutoLabelMeta.model_validate(autolabel) for autolabel in result_rows]


def regenerate_auto_labels():
    pass
