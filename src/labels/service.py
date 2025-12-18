"""
Service functions for labels.
"""

from . import models
from . import schemas
from sqlalchemy.orm import Session, defer
from sqlalchemy import select, insert
from sqlalchemy.exc import IntegrityError, NoResultFound, DataError
from typing import Sequence, Dict, List, Tuple
from .utils import apply_operation
from .exceptions import *
from ..novels.exceptions import NovelNotFoundException, RawChapterRevisionNotFoundException, RawChapterRevisionNotFinalException
from psycopg2 import errorcodes, Error as PgError
from ..novels import models as novel_models
from ..novels.service import query_raw_chapter_revision_by_id
from ..autolabels import models as autolabel_models
from ..autolabels.constants import AutoLabelProgress
from ..auth.models import User
from ..auth.constants import UserType

def query_label_groups_by_user(db : Session, current_user : User) -> Sequence[models.LabelGroup]:
    """
    Queries all label groups that belong to current_user.

    Args:
        db: Database that we query from.
        current_user: Current user.
    """
    q = select(models.LabelGroup).where(models.LabelGroup.user_id == current_user.user_id)
    result = db.execute(q)
    result_rows = result.scalars().all()
    return result_rows

def query_label_group_by_id(db : Session, current_user : User, label_group_id : int) -> models.LabelGroup:
    """
    Queries a label group with specified id.

    Args:
        db: Database that we query from.
        current_user: Current user.
        label_group_id: id of label group to query.
    
    Raises:
        LabelGroupNotFoundException: No label group was found.
        InsufficientPermissionsException: Current user does not have permissions to access this label group
    """
    q = select(models.LabelGroup).where(models.LabelGroup.label_group_id == label_group_id)
    try:
        result = db.execute(q)
        result_row = result.scalar_one()
    except NoResultFound as e:
        raise LabelGroupNotFoundException(str(e))
    if result_row.user_id != current_user.user_id:
        raise InsufficientPermissionsException
    return result_row

def query_label_datas_by_raw_chapter_revision_ids(db : Session, current_user : User, label_group_id : int, raw_chapter_revision_ids : List[int] | None) -> Dict[int, models.LabelData]:
    """
    Query all label datas in some label_group_id with chapter num belonging to some specified list. Return in dictionary in the format
        raw_chapter_revision_id : LabelData

    Args:
        db: Database to query from.
        current_user: Current user.
        label_group_id: id of label group to query from.
        raw_chapter_revision_ids: list of ids for raw chapters corresponding to label datas

    Raises:
        LabelGroupNotFoundException: If the original label group was not found.
        InsufficientPermissionsException: If the user has insufficient permissions to access the label group.
    """
    if raw_chapter_revision_ids is not None and len(raw_chapter_revision_ids) == 0:
        query_label_group_by_id(db, current_user, label_group_id)
        return {}
    q = select(
        models.LabelData
    ).join(
        models.LabelGroup
    ).where(
        models.LabelData.label_group_id == models.LabelGroup.label_group_id
    ).where(
        models.LabelData.label_group_id == label_group_id
    ).where(
        models.LabelGroup.user_id == current_user.user_id
    )
    if raw_chapter_revision_ids:
        q = q.where(
            models.LabelData.raw_chapter_revision_id.in_(raw_chapter_revision_ids)
        )
    result = db.execute(q)
    result_rows = result.scalars().all()

    if len(result_rows) == 0:
        query_label_group_by_id(db, current_user, label_group_id)
    return {x.raw_chapter_revision_id : x for x in result_rows}

def query_label_data_by_id(db : Session, current_user : User, label_data_id : int) -> models.LabelData:
    """
    Query a label data by id.

    Args:
        db: Database to query from.
        current_user: Current user.
        request: Metadata for creating label group.

    Raises:
        LabelDataNotFoundException: Label data not found.
        InsufficientPermissionsException: Current user does not have permission to access this label data.
    """
    q = select(
        models.LabelData, models.LabelGroup.user_id
    ).join(
        models.LabelGroup
    ).where(
        models.LabelData.label_group_id == models.LabelGroup.label_group_id
    ).where(
        models.LabelData.label_data_id == label_data_id
    )
    try:
        result = db.execute(q)
        label_data, user_id = result.one()
    except NoResultFound as e:
        raise LabelDataNotFoundException(str(e))
    if user_id != current_user.user_id:
        raise InsufficientPermissionsException
    return label_data

def _query_labels_by_label_data_id(db : Session, label_data_id : int) -> Sequence[models.Label]:
    """
    Returns a list of all labels corresponding to a label data. Performs no security checks.

    Args:
        db: Database to query from.
        label_data_id: id of label data to retrieve.
    """
    q = select(
        models.Label
    ).where(
        models.Label.label_data_id == label_data_id
    ).order_by(models.Label.label_start)
    result = db.execute(q)
    result_rows = result.scalars().all()
    return result_rows

def query_labels_by_label_data_id(db : Session, current_user : User, label_data_id : int) -> Sequence[models.Label]:
    """
    Returns a list of all labels corresponding to a label data.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_data_id: id of label data.
    
    Raises:
        LabelDataNotFoundException: Label data not found.
        InsufficientPermissionsException: Current user does not have permission to access this label data.
    """
    query_label_data_by_id(db, current_user, label_data_id)
    return _query_labels_by_label_data_id(db, label_data_id)


def insert_label_group(db : Session, current_user : User, request : schemas.CreateLabelGroup) -> models.LabelGroup:
    """
    Creates a label group.

    Args:
        db: Database to query from.
        current_user: Current user.
        request: Metadata for creating label group.
    
    Raises:
        NovelNotFoundException: Novel attached to label group not found in database.
        LabelGroupNameDuplicateException: Current user already has a label group with this name.
        DataTooLongException: Some field data was too long.
        InsufficientPermissionsException: Probably in the future only certain types of users will have permission to label, TBD.
        UnknownError: Some other error occurred.
    """
    label_group = models.LabelGroup(**request.model_dump(), user_id=current_user.user_id)
    try:
        db.add(label_group)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise NovelNotFoundException(str(e.orig))
            if pgcode == errorcodes.UNIQUE_VIOLATION:
                raise LabelGroupNameDuplicateException(str(e.orig))
        raise UnknownError(str(e.orig))
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException(str(e.orig))
        raise UnknownError(e)
    return label_group

def modify_label_group(db : Session, current_user : User, label_group_id : int, request : schemas.UpdateLabelGroup) -> models.LabelGroup:
    """
    Modifies a label group with specified id.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_group_id: id of label group.
        request: Update info.
    
    Raises:
        LabelGroupNotFoundException: No label group was found.
        InsufficientPermissionsException: Current user does not have permissions to access this label group.
        DataTooLongException: Field data too long.
    """
    label_group = query_label_group_by_id(db, current_user, label_group_id)
    try:
        label_group.label_group_name = request.label_group_name
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException(str(e.orig))
        raise UnknownError(e)
    return label_group

def insert_label_data(db : Session, current_user : User, label_group_id : int, request : schemas.CreateLabelData) -> models.LabelData:
    """
    Inserts a label data object into the database.

    Args:
        db: Database to insert into.
        current_user: Current user.
        label_group_id: Label group this label data belongs to.
        request: Metadata for label data.

    Raises:
        RawChapterRevisionNotFoundException: If raw chapter revision with request.raw_chapter_revision not found.
        LabelGroupNotFoundException: If label group with label_group_id not found.
        InsufficientPermissionsException: If current user does not have permission to access this label group.
        LabelDataRevisionDuplicateException: If a label data with this chapter revision in this label group already exists.
    """
    q = select(
        models.LabelGroup, novel_models.RawChapterRevision, novel_models.Novel
    ).options(
        defer(novel_models.RawChapterRevision.raw_chapter_revision_title),
        defer(novel_models.RawChapterRevision.raw_chapter_revision_text),
        defer(novel_models.Novel.novel_title),
        defer(novel_models.Novel.novel_description),
        defer(novel_models.Novel.novel_author)
    ).select_from(
        models.LabelGroup
    ).outerjoin(
        novel_models.RawChapterRevision, 
        novel_models.RawChapterRevision.raw_chapter_revision_id == request.raw_chapter_revision_id
    ).outerjoin(
        novel_models.RawChapter, 
        novel_models.RawChapter.raw_chapter_id == novel_models.RawChapterRevision.raw_chapter_id
    ).outerjoin(
        novel_models.Novel,
        novel_models.Novel.novel_id == novel_models.RawChapter.novel_id
    ).where(
        models.LabelGroup.label_group_id == label_group_id
    )
    try:
        result = db.execute(q)
        result_row = result.one_or_none()
    except Exception as e:
        raise UnknownError(e)
    
    if result_row is None:
        raise LabelGroupNotFoundException("Label group not found.")
    l, r, _ = result_row
    label_group : models.LabelGroup = l
    revision : novel_models.RawChapterRevision | None = r
    if label_group.user_id != current_user.user_id:
        raise InsufficientPermissionsException
    if revision is None:
        raise RawChapterRevisionNotFoundException
    if not revision.raw_chapter_revision_is_final:
        raise RawChapterRevisionNotFinalException
    
    try:
        label_data = models.LabelData(label_group_id=label_group.label_group_id, raw_chapter_revision_id=revision.raw_chapter_revision_id)
        db.add(label_data)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.UNIQUE_VIOLATION:
                raise LabelDataRevisionDuplicateException
        raise UnknownError(e)
    except Exception as e:
        raise UnknownError(e)
    
    return label_data

def modify_label_data_by_stream(db : Session, current_user : User, label_data_id : int, request : schemas.UpdateLabelDataStream) -> None:
    """
    Processes a stream of label datas

    Args:
        db: Database being modified
        current_user: User performing the modification
        label_data_id: id of label data being modified

    Raises:
        LabelDataNotFoundException: Label data not found.
        InsufficientPermissionsException: Current user does not have permission to access this label data.
        LabelNotExistsInvalidOperationException:
        LabelWordMismatchInvalidOperationException:
        LabelAlreadyExistsInvalidOperationException:
    """
    label_data = query_label_data_by_id(db, current_user, label_data_id)
    labels = _query_labels_by_label_data_id(db, label_data_id)
    label_dict = {(label.label_start, label.label_end) : label for label in labels}
    chapter_revision = query_raw_chapter_revision_by_id(db, current_user, label_data.raw_chapter_revision_id)
    try:
        for op in request.ops:
            apply_operation(db, label_data_id, chapter_revision.raw_chapter_revision_text, label_dict, op)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.EXCLUSION_VIOLATION:
                raise LabelExclusionViolationInvalidOperationException
        raise UnknownError(e)
    except Exception as e:
        db.rollback()
        raise e
    
def insert_label_datas_by_autolabels(
        db : Session, 
        current_user : User, 
        label_group_id : int,
        request : schemas.CreateLabelDataByAutoLabel
    ) -> schemas.CreateLabelDataByAutoLabelStatus:
    """
    Move autolabels from the autolabels table over to label_datas/labels. Will try to insert each new label_data and all labels associated with it. Best effort function - try to insert as many new label_datas as possible, and log the errors in the return value. Successful inserts logged as raw_chapter_revision_id, and errors logged as pairs of (raw_chapter_revision_id, message)

    Args:
        db: Database being used.
        current_user: User performing the operation.
        label_group_id: id of label group to attach new label_datas to.
        request: Parameters to specify which autolabels get processed.
    
    Todo:
        Right now, label inserts are being done chapter by chapter. This requires one message sent to database per chapter. We would ideally like to minimize the amount of communication being done between the database and the backend. To accomplish this, we will batch database communication into bundles of 50 chapters each and perform chapter-by-chapter message sending on a bundle only if that bundle fails on initial update. 

        Note this can probably be optimized further, but not sure if it's worth it. 
    """
    # user validation
    label_group = query_label_group_by_id(db, current_user, label_group_id)

    q = select(
        autolabel_models.AutoLabel, novel_models.RawChapterRevision
    ).join(
        novel_models.RawChapterRevision,
        novel_models.RawChapterRevision.raw_chapter_revision_id == autolabel_models.AutoLabel.raw_chapter_revision_id
    ).join(
        novel_models.RawChapter,
        novel_models.RawChapter.raw_chapter_id == novel_models.RawChapterRevision.raw_chapter_id
    ).join(
        novel_models.Novel,
        novel_models.Novel.novel_id == novel_models.RawChapter.novel_id
    ).where(
        autolabel_models.AutoLabel.auto_label_model_name == request.model_name
    ).where(
        autolabel_models.AutoLabel.auto_label_model_params == request.model_params
    ).where(
        autolabel_models.AutoLabel.auto_label_status == AutoLabelProgress.DONE
    ).where(
        novel_models.Novel.novel_id == label_group.novel_id
    )
    if request.raw_chapter_ids is not None and len(request.raw_chapter_ids) > 0:
        q = q.where(novel_models.RawChapter.raw_chapter_id.in_(request.raw_chapter_ids))
    if request.raw_chapter_revision_ids is not None and len(request.raw_chapter_revision_ids) > 0:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_id.in_(request.raw_chapter_revision_ids))
    if request.start is not None:
        q = q.where(novel_models.RawChapter.raw_chapter_num >= request.start)
    if request.end is not None:
        q = q.where(novel_models.RawChapter.raw_chapter_num < request.end)
    if current_user.user_type != UserType.ADMIN:
        q = q.where(novel_models.RawChapterRevision.raw_chapter_revision_is_public == True)
    result = db.execute(q)

    success : List[int] = []
    errors : List[Tuple[int, str]] = []

    for a, r in result:
        autolabel : autolabel_models.AutoLabel = a
        revision : novel_models.RawChapterRevision = r
        try:
            if not all(revision.raw_chapter_revision_text[label['label_start']:label['label_end']] == label['label_word'] for label in autolabel.auto_label_data):
                raise LabelWordMismatchInvalidOperationException
            with db.begin_nested():
                stmt = insert(models.LabelData).values(
                    {
                        "label_group_id" : label_group_id,
                        "raw_chapter_revision_id" : autolabel.raw_chapter_revision_id
                    }
                ).returning(
                    models.LabelData.label_data_id
                )
                label_data_id = db.execute(stmt).scalar_one()
                if autolabel.auto_label_data:
                    stmt = insert(models.Label).values([{**label, 'label_data_id' : label_data_id} for label in autolabel.auto_label_data])
                    db.execute(stmt)
                success.append(autolabel.raw_chapter_revision_id)
        except IntegrityError as e:
            if isinstance(e.orig, PgError):
                pgcode = e.orig.pgcode
                if pgcode == errorcodes.UNIQUE_VIOLATION:
                    errors.append((autolabel.raw_chapter_revision_id, f"Failed insert for chapter revision with id {autolabel.raw_chapter_revision_id}, autolabel id {autolabel.auto_label_id} due to label data for label group already existing."))
                elif pgcode == errorcodes.EXCLUSION_VIOLATION:
                    errors.append((autolabel.raw_chapter_revision_id, f"Failed insert for chapter revision with id {autolabel.raw_chapter_revision_id}, autolabel id {autolabel.auto_label_id} due to labels in autolabel data overlapping."))
                else:
                    errors.append((autolabel.raw_chapter_revision_id, f"Failed insert for chapter revision with id {autolabel.raw_chapter_revision_id}, autolabel id {autolabel.auto_label_id} due to unknown reason: {str(e.orig)}"))
            else:
                errors.append((autolabel.raw_chapter_revision_id, f"Failed insert for chapter revision with id {autolabel.raw_chapter_revision_id}, autolabel id {autolabel.auto_label_id} due to unknown reason: {str(e)}"))
        except Exception as e:
            errors.append((autolabel.raw_chapter_revision_id, f"Failed insert for chapter revision with id {autolabel.raw_chapter_revision_id}, autolabel id {autolabel.auto_label_id} due to unknown reason: {str(e)}"))
    try:
        db.commit()
    except Exception as e:
        raise UnknownError(e)
    return schemas.CreateLabelDataByAutoLabelStatus(success=success, errors=errors)

    