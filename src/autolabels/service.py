"""
Service functions for auto labeling.

Todo: Rewrite to use more raw sql. This seems like a huge pain in the ass so I am putting this off indefinitely.
"""

from typing import List, Dict, Tuple
from sqlalchemy.orm import Session, defer
from sqlalchemy import select, and_
from sqlalchemy.exc import NoResultFound, IntegrityError
from psycopg2 import errorcodes, Error as PgError
from uuid import uuid4
import asyncio

from . import models
from . import schemas
from .utils import AutoLabelDispatcher
from ..auth.constants import UserType
from ..auth.models import User, UserType
from .exceptions import *
from ..exceptions import *
from .constants import *
from ..novels import models as novel_models
from ..novels.permissions import *

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
        raise AutoLabelNotFoundException(str(e))
    if current_user.user_type != UserType.ADMIN and not is_public:
        raise InsufficientPermissionsException
    return auto_label

def query_auto_labels(
        db : Session, 
        current_user : User, 
        novel_id : int, 
        raw_chapter_ids : List[int] | None, 
        raw_chapter_revision_ids : List[int] | None,  
        start : int | None, 
        end : int | None, 
        model_names : List[str] | None, 
    ) -> Dict[int, schemas.AutoLabelMeta]:
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
        novel_models.RawChapterRevision.raw_chapter_revision_is_final == True
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
    q = novel_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()

    return {row.raw_chapter_revision_id : schemas.AutoLabelMeta.model_validate(row) for row in result_rows}

async def insert_auto_labels(db : Session, current_user : User, dispatcher : AutoLabelDispatcher, request : schemas.CreateAutoLabels) -> schemas.CreateAutoLabelsStatus:
    """
    Idempotent insert of autolabels that separates new entries from existing ones.
    1. Queries all requested revision IDs to check if the specific model config already exists.
    2. Separates results into 'inserts' (newly created) and 'exists' (pre-existing duplicates).
    3. Bulk inserts and queues jobs for the new entries.

    Args:
        db: Database to insert into.
        current_user: User performing the action.
        request: Request metadata.
    
    Raises:
        AutoLabelDuplicateException: If insertion violates a unique constraint. Will most likely occur when there is a race condition.
    
    Notes:
        This function ignores all revision IDs that do not exist, revisions that are not final, and revisions that the user has insufficient permissions for.
    """
    # select pairs of the form
    # (raw_chapter_revision_id, AutoLabel where revision id/model name/params match OR None if such an AutoLabel does not exist)
    # should only return one such pair per raw_chapter_revision_id due to UniqueConstraints on autolabels table
    q = select(
        novel_models.RawChapterRevision, 
        models.AutoLabel
    ).options(
        defer(models.AutoLabel.auto_label_data),
        defer(novel_models.RawChapterRevision.raw_chapter_revision_text)
    ).outerjoin(
        models.AutoLabel,
        and_(
            models.AutoLabel.raw_chapter_revision_id == novel_models.RawChapterRevision.raw_chapter_revision_id,
            models.AutoLabel.auto_label_model_name == request.auto_label_model_name,
            models.AutoLabel.auto_label_model_params == request.auto_label_model_params
        )
    ).join(
        novel_models.RawChapter,
        novel_models.RawChapter.raw_chapter_id == novel_models.RawChapterRevision.raw_chapter_id
    ).join(
        novel_models.Novel,
        novel_models.Novel.novel_id == novel_models.RawChapter.novel_id
    ).where(
        novel_models.RawChapterRevision.raw_chapter_revision_is_final == True
    ).where(
        novel_models.Novel.novel_id == request.novel_id
    )
    if request.raw_chapter_ids is not None and len(request.raw_chapter_ids) > 0:
        q = q.where(novel_models.RawChapter.raw_chapter_id.in_(request.raw_chapter_ids))
    if request.raw_chapter_revision_ids is not None and len(request.raw_chapter_revision_ids) > 0:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_id.in_(request.raw_chapter_revision_ids))
    if request.start is not None:
        q = q.where(novel_models.RawChapter.raw_chapter_num >= request.start)
    if request.end is not None:
        q = q.where(novel_models.RawChapter.raw_chapter_num < request.end)
    if request.is_primary is not None:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_is_primary == request.is_primary)
    if request.is_public is not None:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_is_public == request.is_public)
    q = novel_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.all()
    
    exists : Dict[int, schemas.AutoLabelMeta] = {}
    to_insert : List[Tuple[int, models.AutoLabel, bool]] = []
    inserts : Dict[int, Tuple[schemas.AutoLabelMeta, bool]] = {}
    for r, a in result_rows:
        # type hinting (is there a better way? idk)
        revision : novel_models.RawChapterRevision = r
        autolabel : models.AutoLabel | None = a
        if autolabel is not None:
            exists[revision.raw_chapter_revision_id] = schemas.AutoLabelMeta.model_validate(autolabel)
        else:
            new_autolabel = models.AutoLabel(
                auto_label_model_name=request.auto_label_model_name,
                auto_label_model_params=request.auto_label_model_params,
                auto_label_status=AutoLabelProgress.PENDING,
                raw_chapter_revision_id=revision.raw_chapter_revision_id,
                auto_label_message="Waiting to be queued."
            )
            to_insert.append((revision.raw_chapter_revision_id, new_autolabel, False))

    try:
        db.add_all([temp[1] for temp in to_insert])
        db.commit()
    except IntegrityError as e:
        db.rollback()
        assert isinstance(e.orig, PgError)
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.UNIQUE_VIOLATION:
            raise AutoLabelDuplicateException(str(e.orig))
        raise UnknownError(e)
    except Exception as e:
        db.rollback()
        raise UnknownError(e)
    
    tasks = []
    for _, autolabel, _ in to_insert:
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
        raise UnknownError(e)
    
    ret = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i in range(len(ret)):
        revision_id, autolabel, _ = to_insert[i]
        if ret[i] is None:
            autolabel.auto_label_message = "Job queued."
            to_insert[i] = (revision_id, autolabel, True)
        else:
            autolabel.auto_label_message = "Job failed to queue."
            autolabel.auto_label_status = AutoLabelProgress.FAILED
    try:
        db.commit()
    except Exception as e:
        raise UnknownError(e)
    
    inserts = {revision_id : (schemas.AutoLabelMeta.model_validate(autolabel), success) for revision_id, autolabel, success in to_insert}
    return schemas.CreateAutoLabelsStatus(inserts=inserts, exists=exists)


def regenerate_auto_labels():
    pass