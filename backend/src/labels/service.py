"""
Service functions for labels.
"""
import uuid
from collections.abc import Sequence

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from sqlalchemy import func, insert, literal, select, update
from sqlalchemy.exc import DataError, IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from ..auth.models import User
from ..autolabels import models as autolabel_models
from ..autolabels.constants import AutoLabelProgress
from ..exceptions import DataTooLongException, NotFoundException, UnknownError
from ..novels import models as novel_models
from ..novels.exceptions import NovelNotFoundException, RevisionTextNotFoundException
from ..novels.permissions import revision_text_mod_access_select
from . import models, schemas
from .constants import LabelRole
from .exceptions import (
    LabelDataNotFoundException,
    LabelDataRevisionDuplicateException,
    LabelGroupNotFoundException,
    LabelWordMismatchInvalidOperationException,
)
from .permissions import (
    label_data_mod_access_insert,
    label_data_mod_access_select,
    label_group_mod_access_insert,
    label_group_mod_access_select,
    label_group_mod_access_update,
)
from .utils import apply_operation


def query_label_groups(db : Session, current_user : User, novel_id : uuid.UUID) -> Sequence[models.LabelGroup]:
    """
    Queries all label groups that belong to current_user.

    Args:
        db: Database that we query from.
        current_user: Current user.
        novel_id: id of novel to query label groups for.
    """
    q = select(models.LabelGroup).where(models.LabelGroup.novel_id == novel_id)
    q = label_group_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()
    return result_rows

def query_label_group_by_id(db : Session, current_user : User, label_group_id : uuid.UUID) -> models.LabelGroup:
    """
    Queries a label group with specified id.

    Args:
        db: Database that we query from.
        current_user: Current user.
        label_group_id: id of label group to query.

    Raises:
        LabelGroupNotFoundException: No label group was found.
    """
    q = select(models.LabelGroup).where(models.LabelGroup.label_group_id == label_group_id)
    q = label_group_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        result_row = result.scalar_one()
    except NoResultFound as e:
        raise LabelGroupNotFoundException from e
    return result_row

def query_label_datas(db : Session, current_user : User, label_group_id : uuid.UUID, start : int | None, end : int | None) -> Sequence[models.LabelData]:
    """
    Query all label datas in some label_group_id with certain criteria.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_group_id: id of label group to query from.
        start: If specified, only return label datas with chapter num >= start.
        end: If specified, only return label datas with chapter num < end.
    """
    q = select(
        models.LabelData
    ).where(
        models.LabelData.label_group_id == label_group_id
    ).join(
        novel_models.RevisionText,
        novel_models.RevisionText.revision_text_id == models.LabelData.revision_text_id
   ).join(novel_models.Revision,
        novel_models.Revision.revision_id == novel_models.RevisionText.revision_id
    ).join(
        novel_models.Chapter,
        novel_models.Chapter.chapter_id == novel_models.Revision.chapter_id
    ).where(
        novel_models.RevisionText.revision_text_version == select(
            func.max(novel_models.RevisionText.revision_text_version)
        ).where(
            novel_models.RevisionText.revision_id == novel_models.Revision.revision_id
        ).correlate(novel_models.Revision).scalar_subquery()
    )
    q = label_group_mod_access_select(q, current_user)
    if start is not None:
        q = q.where(novel_models.Chapter.chapter_num >= start)
    if end is not None:
        q = q.where(novel_models.Chapter.chapter_num < end)
    q = q.order_by(novel_models.Chapter.chapter_num, novel_models.Revision.revision_id)
    result = db.execute(q)
    result_rows = result.scalars().all()
    return result_rows

def query_label_data_by_id(db : Session, current_user : User, label_data_id : uuid.UUID) -> models.LabelData:
    """
    Query a label data by id.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_data_id: id of label data to retrieve.

    Raises:
        LabelDataNotFoundException: Label data not found.
    """
    q = select(
        models.LabelData
    ).where(
        models.LabelData.label_data_id == label_data_id
    )
    q = label_data_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        label_data = result.scalar_one()
    except NoResultFound as e:
        raise LabelDataNotFoundException from e
    return label_data

def query_labels_by_label_data_id(db : Session, current_user : User, label_data_id : uuid.UUID) -> Sequence[models.Label]:
    """
    Returns a list of all labels corresponding to a label data.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_data_id: id of label data.
    """
    q = select(
        models.Label
    ).select_from(
        models.LabelData
    ).where(
        models.Label.label_data_id == label_data_id
    ).join(
        models.Label,
        models.LabelData.label_data_id == models.Label.label_data_id
    ).order_by(models.Label.label_start)
    q = label_data_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()
    return result_rows

def insert_label_group(db : Session, current_user : User, request : schemas.CreateLabelGroup) -> models.LabelGroup:
    """
    Creates a label group.

    Args:
        db: Database to query from.
        current_user: Current user.
        request: Metadata for creating label group.

    Raises:
        NovelNotFoundException: Novel attached to label group not found in database.
        DataTooLongException: Some field data was too long.
    """
    data = list(request.model_dump().items())
    vals = select(
        *[literal(v) for _, v in data]
    )
    vals = label_group_mod_access_insert(vals, current_user, request.novel_id)
    cols = [k for k, _ in data]

    stmt = insert(models.LabelGroup).from_select(
        cols, vals
    ).returning(models.LabelGroup)
    try:
        result = db.execute(stmt)
        label_group = result.scalar_one()
        stmt = insert(models.LabelContributor).values(
            {
                "label_group_id" : label_group.label_group_id,
                "user_id" : current_user.user_id,
                "label_contributor_role" : LabelRole.OWNER
            }
        )
        db.execute(stmt)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise NovelNotFoundException from e
        raise UnknownError from e
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        raise NovelNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return label_group

def modify_label_group(db : Session, current_user : User, label_group_id : uuid.UUID, request : schemas.UpdateLabelGroup) -> models.LabelGroup:
    """
    Modifies a label group with specified id.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_group_id: id of label group.
        request: Update info.

    Raises:
        LabelGroupNotFoundException: No label group was found.
        DataTooLongException: Field data too long.
    """
    stmt = update(
        models.LabelGroup
    ).where(
        models.LabelGroup.label_group_id == label_group_id
    ).values(
        **request.model_dump(exclude_unset=True)
    ).returning(models.LabelGroup)
    stmt = label_group_mod_access_update(stmt, current_user)
    try:
        result = db.execute(stmt)
        label_group = result.scalar_one()
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        raise LabelGroupNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return label_group

def insert_label_data(db : Session, current_user : User, label_group_id : uuid.UUID, request : schemas.CreateLabelData) -> models.LabelData:
    """
    Inserts a label data object into the database.

    Args:
        db: Database to insert into.
        current_user: Current user.
        label_group_id: Label group this label data belongs to.
        request: Metadata for label data.

    Raises:
        NotFoundException: If revision with request.revision_id not found.
        LabelGroupNotFoundException: If label group with label_group_id not found.
        LabelDataRevisionDuplicateException: If a label data with this revision in this label group already exists.
        NotFoundException: Either revision or label group not found.
    """
    data = list(request.model_dump().items())
    data.append(("label_group_id", label_group_id))
    cols = [k for k, _ in data]

    vals = select(
        *[literal(v) for _, v in data]
    )
    vals = label_data_mod_access_insert(vals, current_user, label_group_id)
    stmt = insert(models.LabelData).from_select(
        cols,
        vals
    ).returning(models.LabelData)
    try:
        result = db.execute(stmt)
        label_data = result.scalar_one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise NotFoundException("Either revision or label group not found.") from e
            elif pgcode == errorcodes.UNIQUE_VIOLATION:
                raise LabelDataRevisionDuplicateException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        raise LabelGroupNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return label_data

def modify_label_data_by_stream(db : Session, current_user : User, label_data_id : uuid.UUID, request : schemas.UpdateLabelDataStream) -> None:
    """
    Processes a stream of label datas

    Args:
        db: Database being modified
        current_user: User performing the modification
        label_data_id: id of label data being modified

    Raises:
        RevisionTextNotFoundException: If the revision text associated with the label data is not found.
        LabelOutOfBoundsInvalidOperationException: If an operation refers to positions outside the text bounds.
        LabelWordMismatchInvalidOperationException: If the word provided in an operation does not match the text at the specified positions.
        LabelDataNotFoundException: If the LabelData does not exist or the user lacks permissions.
        LabelExclusionViolationInvalidOperationException: If an add/update operation creates an overlapping label (exclusion constraint violation).
        LabelNotExistsInvalidOperationException: If a delete operation targets a label that does not exist.
        LabelInvalidOperationException: If an update operation is malformed (e.g. setting a new word without moving the label).
    """
    q = select(
        novel_models.RevisionText.revision_text_content
    ).select_from(
        models.LabelData
    ).where(
        models.LabelData.label_data_id == label_data_id
    ).join(
        novel_models.RevisionText,
        novel_models.RevisionText.revision_text_id == models.LabelData.revision_text_id
    )
    q = revision_text_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        text = result.scalar_one()
    except NoResultFound as e:
        raise RevisionTextNotFoundException from e
    except Exception as e:
        raise UnknownError from e
    try:
        for op in request.ops:
            apply_operation(db, current_user, label_data_id, text, op)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def insert_label_datas_by_autolabels(
        db : Session,
        current_user : User,
        label_group_id : uuid.UUID,
        request : schemas.CreateLabelDataByAutoLabel
    ) -> schemas.CreateLabelDataByAutoLabelStatus:
    """
    Move autolabels from the autolabels table over to label_datas/labels. Will try to insert each new label_data and all labels associated with it. Best effort function - try to insert as many new label_datas as possible, and log the errors in the return value. Successful inserts logged as revision_id, and errors logged as pairs of (revision_id, message)

    Args:
        db: Database being used.
        current_user: User performing the operation.
        label_group_id: id of label group to attach new label_datas to.
        request: Parameters to specify which autolabels get processed.

    Todo:
        Right now, label inserts are being done chapter by chapter. This requires one message sent to database per chapter. We would ideally like to minimize the amount of communication being done between the database and the backend. To accomplish this, we will batch database communication into bundles of n chapters each and perform chapter-by-chapter message sending on a bundle only if that bundle fails on initial update.

        Note this can probably be optimized further, but not sure if it's worth it.
    """
    q = select(
        autolabel_models.AutoLabel, novel_models.RevisionText
    ).select_from(
        autolabel_models.AutoLabel
    ).join(
        models.LabelGroup,
        models.LabelGroup.label_group_id == label_group_id
    ).join(
        novel_models.RevisionText,
        novel_models.RevisionText.revision_text_id == autolabel_models.AutoLabel.revision_text_id
    ).join(
        novel_models.Revision,
        novel_models.Revision.revision_id == novel_models.RevisionText.revision_id
    ).join(
        novel_models.Chapter,
        novel_models.Chapter.chapter_id == novel_models.Revision.chapter_id
    ).join(
        novel_models.Novel,
        novel_models.Novel.novel_id == novel_models.Chapter.novel_id
    ).where(
        autolabel_models.AutoLabel.auto_label_model_name == request.model_name
    ).where(
        autolabel_models.AutoLabel.auto_label_model_params == request.model_params
    ).where(
        autolabel_models.AutoLabel.auto_label_status == AutoLabelProgress.DONE
    ).where(
        novel_models.Novel.novel_id == models.LabelGroup.novel_id
    ).where(
        novel_models.RevisionText.revision_text_version == select(
            func.max(novel_models.RevisionText.revision_text_version)
        ).where(
            novel_models.RevisionText.revision_id == novel_models.Revision.revision_id
        ).correlate(novel_models.Revision).scalar_subquery()
    )
    q = label_group_mod_access_select(q, current_user)
    if request.chapter_ids is not None and len(request.chapter_ids) > 0:
        q = q.where(novel_models.Chapter.chapter_id.in_(request.chapter_ids))
    if request.revision_ids is not None and len(request.revision_ids) > 0:
        q = q.where(novel_models.RevisionText.revision_text_id.in_(request.revision_ids))
    if request.start is not None:
        q = q.where(novel_models.Chapter.chapter_num >= request.start)
    if request.end is not None:
        q = q.where(novel_models.Chapter.chapter_num < request.end)
    result = db.execute(q)

    success : list[uuid.UUID] = []
    errors : list[tuple[uuid.UUID, str]] = []

    for a, r in result:
        autolabel : autolabel_models.AutoLabel = a
        revision_text : novel_models.RevisionText = r
        try:
            if not all(revision_text.revision_text_content[label['label_start']:label['label_end']] == label['label_word'] for label in autolabel.auto_label_data):
                raise LabelWordMismatchInvalidOperationException("Text mismatch between autolabel and chapter")
            with db.begin_nested():
                vals = select(
                    literal(label_group_id),
                    literal(autolabel.revision_text_id)
                )
                cols = [
                    models.LabelData.label_group_id,
                    models.LabelData.revision_text_id
                ]
                vals = label_data_mod_access_insert(vals, current_user, label_group_id)
                stmt = insert(models.LabelData).from_select(
                    cols,
                    vals
                ).returning(
                    models.LabelData.label_data_id
                )
                label_data_id = db.execute(stmt).scalar_one()
                if autolabel.auto_label_data:
                    stmt = insert(models.Label).values([{**label, 'label_data_id' : label_data_id} for label in autolabel.auto_label_data])
                    db.execute(stmt)
                success.append(autolabel.revision_text_id)
        except IntegrityError as e:
            if isinstance(e.orig, PgError):
                pgcode = e.orig.pgcode
                if pgcode == errorcodes.UNIQUE_VIOLATION:
                    errors.append((autolabel.revision_text_id, f"Failed insert for revision text with id {autolabel.revision_text_id}, autolabel id {autolabel.auto_label_id} due to label data for label group already existing."))
                elif pgcode == errorcodes.EXCLUSION_VIOLATION:
                    errors.append((autolabel.revision_text_id, f"Failed insert for revision text with id {autolabel.revision_text_id}, autolabel id {autolabel.auto_label_id} due to labels in autolabel data overlapping."))
                else:
                    errors.append((autolabel.revision_text_id, f"Failed insert for revision text with id {autolabel.revision_text_id}, autolabel id {autolabel.auto_label_id} due to unknown reason: {str(e.orig)}"))
            else:
                errors.append((autolabel.revision_text_id, f"Failed insert for revision text with id {autolabel.revision_text_id}, autolabel id {autolabel.auto_label_id} due to unknown reason: {str(e)}"))
        except NoResultFound as e:
            errors.append((autolabel.revision_text_id, f"Failed insert for revision text with id {autolabel.revision_text_id}, autolabel id {autolabel.auto_label_id} due to insufficient permissions: {str(e)}"))
        except Exception as e:
            errors.append((autolabel.revision_text_id, f"Failed insert for revision text with id {autolabel.revision_text_id}, autolabel id {autolabel.auto_label_id} due to unknown reason: {str(e)}"))
    try:
        db.commit()
    except Exception as e:
        raise UnknownError from e
    return schemas.CreateLabelDataByAutoLabelStatus(success=success, errors=errors)

