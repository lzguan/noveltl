from sqlalchemy.orm import Session, defer
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from typing import Sequence, List
from . import models
from . import schemas
from .exceptions import *

from ..auth.models import User, UserType
from ..novels import models as novel_models

def query_auto_label_by_id(db : Session, current_user : User, auto_label_id : int) -> models.AutoLabel:
    """
    Query an autolabel with a specific id from database.

    Args:
        db: Databse to query from.
        current_user: User querying the autolabel.
        autolabel_id: id of autolabel to query.
    
    Raises:
        AutoLabelNotFoundException: Auto label not found in database.
    """
    q = select(
        models.AutoLabel
    ).join(
        novel_models.RawChapterRevision, 
        novel_models.RawChapterRevision.raw_chapter_revision_id == models.AutoLabel.raw_chapter_revision_id
    ).where(
        models.AutoLabel.auto_label_id == auto_label_id
    )
    if current_user.user_type != UserType.ADMIN:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_is_public == True)
    try:
        result = db.execute(q)
        auto_label = result.scalar_one()
    except NoResultFound as e:
        raise AutoLabelNotFoundException(str(e))
    return auto_label

def query_auto_labels(
        db : Session, 
        current_user : User, 
        novel_id : int, 
        raw_chapter_ids : List[int] | None, 
        raw_chapter_revision_ids : List[int] | None,  
        start : int | None, 
        end : int | None, 
        model_names : str | None, 
    ) -> Sequence[schemas.AutoLabelMeta]:
    """
    Query auto-labels with filtering and return lightweight metadata.

    Args:
        db: Database session.
        current_user: The user requesting the data. Non-admins only see public revisions.
        novel_id: ID of the novel to filter by.
        raw_chapter_ids: Optional list of chapter IDs to filter.
        raw_chapter_revision_ids: Optional list of revision IDs to filter.
        start: Optional start chapter number (inclusive).
        end: Optional end chapter number (exclusive).
        model_names: Optional names of the auto-label model to filter by.

    Returns:
        Sequence[schemas.AutoLabelMeta]: List of auto-label metadata.
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
    if current_user.user_type != UserType.ADMIN:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_is_public == True)
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
    result = db.execute(q)
    result_rows = result.scalars().all()

    return [schemas.AutoLabelMeta.model_validate(row) for row in result_rows]

def insert_auto_labels(db : Session, current_user : User, request : schemas.CreateAutoLabels) -> models.AutoLabel:
    """
    
    """
    raise Exception
    pass