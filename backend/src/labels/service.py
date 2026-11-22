"""
Service functions for labels.
"""

import logging
import uuid
from collections.abc import Sequence

from psycopg.errors import ForeignKeyViolation, StringDataRightTruncation, UniqueViolation
from sqlalchemy import func, insert, literal, select, update
from sqlalchemy.exc import DataError, IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.exceptions import DataTooLongException, NotFoundException
from src.labels import models, schemas
from src.labels.constants import LabelRole
from src.labels.exceptions import (
    LabelDataNotFoundException,
    LabelDataRevisionDuplicateException,
    LabelGroupNotFoundException,
    LabelNotFoundException,
)
from src.labels.permissions import (
    label_contributors_mod_access_select,
    label_data_mod_access_insert,
    label_data_mod_access_select,
    label_group_mod_access_insert,
    label_group_mod_access_select,
    label_group_mod_access_update,
)
from src.labels.utils import apply_operation
from src.novels import models as novel_models
from src.novels.exceptions import NovelNotFoundException

logger = logging.getLogger(__name__)


async def query_label_groups(db: AsyncSession, current_user: User, novel_id: uuid.UUID) -> Sequence[models.LabelGroup]:
    """
    Queries all label groups that belong to current_user.

    Args:
        db: Database that we query from.
        current_user: Current user.
        novel_id: id of novel to query label groups for.
    """
    q = select(models.LabelGroup).where(models.LabelGroup.novel_id == novel_id)
    q = label_group_mod_access_select(q, current_user)
    result = await db.execute(q)
    result_rows = result.scalars().all()
    return result_rows


async def query_label_groups_with_contributor_info(
    db: AsyncSession, current_user: User, novel_id: uuid.UUID
) -> Sequence[schemas.LabelGroupWithRole]:
    """
    Queries all label groups that belong to current_user, along with the role of the user in each label group.

    Args:
        db: Database that we query from.
        current_user: Current user.
        novel_id: id of novel to query label groups for.
    """
    q = (
        select(models.LabelGroup, models.LabelContributor.label_contributor_role)
        .join(models.LabelContributor, models.LabelContributor.label_group_id == models.LabelGroup.label_group_id)
        .where(models.LabelGroup.novel_id == novel_id)
        .where(models.LabelContributor.user_id == current_user.user_id)
    )
    q = label_group_mod_access_select(q, current_user)
    result = await db.execute(q)
    result_rows = result.all()
    out: list[schemas.LabelGroupWithRole] = []
    for lg, r in result_rows:
        label_group: models.LabelGroup = lg
        role: LabelRole = r
        out.append(schemas.LabelGroupWithRole(label_group=label_group, role=role))

    return out


async def query_label_group_by_id(db: AsyncSession, current_user: User, label_group_id: uuid.UUID) -> models.LabelGroup:
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
        result = await db.execute(q)
        result_row = result.scalar_one()
    except NoResultFound as e:
        raise LabelGroupNotFoundException from e
    return result_row


async def query_label_datas(
    db: AsyncSession, current_user: User, label_group_id: uuid.UUID, start: int | None, end: int | None
) -> Sequence[models.LabelData]:
    """
    Query all label datas in some label_group_id with certain criteria.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_group_id: id of label group to query from.
        start: If specified, only return label datas with chapter num >= start.
        end: If specified, only return label datas with chapter num < end.
    """
    q = (
        select(models.LabelData)
        .where(models.LabelData.label_group_id == label_group_id)
        .join(
            novel_models.ChapterContent,
            novel_models.ChapterContent.chapter_content_id == models.LabelData.chapter_content_id,
        )
        .join(novel_models.Chapter, novel_models.Chapter.chapter_id == novel_models.ChapterContent.chapter_id)
        .where(
            novel_models.ChapterContent.chapter_content_version
            == select(func.max(novel_models.ChapterContent.chapter_content_version))
            .where(novel_models.ChapterContent.chapter_id == novel_models.Chapter.chapter_id)
            .correlate(novel_models.Chapter)
            .scalar_subquery()
        )
    )
    q = label_group_mod_access_select(q, current_user)
    if start is not None:
        q = q.where(novel_models.Chapter.chapter_num >= start)
    if end is not None:
        q = q.where(novel_models.Chapter.chapter_num < end)
    q = q.order_by(novel_models.Chapter.chapter_num, novel_models.ChapterContent.chapter_content_version)
    result = await db.execute(q)
    result_rows = result.scalars().all()
    return result_rows


async def query_label_data_by_id(db: AsyncSession, current_user: User, label_data_id: uuid.UUID) -> models.LabelData:
    """
    Query a label data by id.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_data_id: id of label data to retrieve.

    Raises:
        LabelDataNotFoundException: Label data not found.
    """
    q = select(models.LabelData).where(models.LabelData.label_data_id == label_data_id)
    q = label_data_mod_access_select(q, current_user)
    try:
        result = await db.execute(q)
        label_data = result.scalar_one()
    except NoResultFound as e:
        raise LabelDataNotFoundException from e
    return label_data


async def query_labels_by_label_data_id(
    db: AsyncSession, current_user: User, label_data_id: uuid.UUID
) -> Sequence[models.Label]:
    """
    Returns a list of all labels corresponding to a label data.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_data_id: id of label data.
    """
    q = (
        select(models.Label)
        .select_from(models.LabelData)
        .where(models.Label.label_data_id == label_data_id)
        .join(models.Label, models.LabelData.label_data_id == models.Label.label_data_id)
        .order_by(models.Label.label_start)
    )
    q = label_data_mod_access_select(q, current_user)
    result = await db.execute(q)
    result_rows = result.scalars().all()
    return result_rows


async def query_label_by_id(db: AsyncSession, current_user: User, label_id: uuid.UUID) -> models.Label:
    """Return an accessible label by its ID."""
    q = (
        select(models.Label)
        .select_from(models.LabelData)
        .join(models.Label, models.LabelData.label_data_id == models.Label.label_data_id)
        .where(models.Label.label_id == label_id)
    )
    q = label_data_mod_access_select(q, current_user)
    try:
        return (await db.execute(q)).scalar_one()
    except NoResultFound as e:
        raise LabelNotFoundException from e


async def query_label_contributors_of_label_group(
    db: AsyncSession, current_user: User, label_group_id: uuid.UUID
) -> Sequence[models.LabelContributor]:
    """
    Returns a list of all label contributors corresponding to a label group.

    Args:
        db: Database to query from.
        current_user: Current user.
        label_group_id: id of label group.
    """
    q = select(models.LabelContributor).where(models.LabelContributor.label_group_id == label_group_id)
    q = label_contributors_mod_access_select(q, current_user)
    result = await db.execute(q)
    result_rows = result.scalars().all()
    if len(result_rows) == 0:
        raise LabelGroupNotFoundException
    return result_rows


async def insert_label_group(
    db: AsyncSession, current_user: User, request: schemas.CreateLabelGroup
) -> models.LabelGroup:
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
    vals = select(*[literal(v) for _, v in data])
    vals = label_group_mod_access_insert(vals, current_user, request.novel_id)
    cols = [k for k, _ in data]

    stmt = insert(models.LabelGroup).from_select(cols, vals).returning(models.LabelGroup)
    try:
        result = await db.execute(stmt)
        label_group = result.scalar_one()
        stmt = insert(models.LabelContributor).values(
            {
                "label_group_id": label_group.label_group_id,
                "user_id": current_user.user_id,
                "label_contributor_role": LabelRole.OWNER,
            }
        )
        await db.execute(stmt)
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if isinstance(e.orig, ForeignKeyViolation):
            raise NovelNotFoundException from e
        raise
    except DataError as e:
        await db.rollback()
        if isinstance(e.orig, StringDataRightTruncation):
            raise DataTooLongException from e
        raise
    except NoResultFound as e:
        await db.rollback()
        raise NovelNotFoundException from e
    except Exception:
        await db.rollback()
        raise
    return label_group


async def modify_label_group(
    db: AsyncSession, current_user: User, label_group_id: uuid.UUID, request: schemas.UpdateLabelGroup
) -> models.LabelGroup:
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
    stmt = (
        update(models.LabelGroup)
        .where(models.LabelGroup.label_group_id == label_group_id)
        .values(**request.model_dump(exclude_unset=True))
        .returning(models.LabelGroup)
    )
    stmt = label_group_mod_access_update(stmt, current_user)
    try:
        result = await db.execute(stmt)
        label_group = result.scalar_one()
        await db.commit()
    except DataError as e:
        await db.rollback()
        if isinstance(e.orig, StringDataRightTruncation):
            raise DataTooLongException from e
        raise
    except NoResultFound as e:
        await db.rollback()
        raise LabelGroupNotFoundException from e
    except Exception:
        await db.rollback()
        raise
    return label_group


async def insert_label_data(
    db: AsyncSession, current_user: User, label_group_id: uuid.UUID, request: schemas.CreateLabelData
) -> models.LabelData:
    """
    Inserts a label data object into the database.

    Args:
        db: Database to insert into.
        current_user: Current user.
        label_group_id: Label group this label data belongs to.
        request: Metadata for label data.

    Raises:
        NotFoundException: If chapter content with request.chapter_content_id not found.
        LabelGroupNotFoundException: If label group with label_group_id not found.
        LabelDataRevisionDuplicateException: If a label data with this chapter content in this label group already exists.
        NotFoundException: Either chapter content or label group not found.
    """
    data = list(request.model_dump().items())
    data.append(("label_group_id", label_group_id))
    cols = [k for k, _ in data]

    vals = select(*[literal(v) for _, v in data])
    vals = label_data_mod_access_insert(vals, current_user, label_group_id)
    stmt = insert(models.LabelData).from_select(cols, vals).returning(models.LabelData)
    try:
        result = await db.execute(stmt)
        label_data = result.scalar_one()
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if isinstance(e.orig, ForeignKeyViolation):
            raise NotFoundException("Either chapter content or label group not found.") from e
        if isinstance(e.orig, UniqueViolation):
            raise LabelDataRevisionDuplicateException from e
        raise
    except NoResultFound as e:
        await db.rollback()
        raise LabelGroupNotFoundException from e
    except Exception:
        await db.rollback()
        raise
    return label_data


async def modify_label_data_by_stream(
    db: AsyncSession, current_user: User, label_data_id: uuid.UUID, request: schemas.UpdateLabelDataStream
) -> list[schemas.OpResult]:
    """
    Processes a stream of label datas

    Args:
        db: Database being modified
        current_user: User performing the modification
        label_data_id: id of label data being modified

    Raises:
        ChapterContentNotFoundException: If the chapter content associated with the label data is not found.
        LabelOutOfBoundsInvalidOperationException: If an operation refers to positions outside the text bounds.
        LabelDataNotFoundException: If the LabelData does not exist or the user lacks permissions.
        LabelExclusionViolationInvalidOperationException: If an add/update operation creates an overlapping label (exclusion constraint violation).
        LabelNotExistsInvalidOperationException: If a delete operation targets a label that does not exist.
        LabelInvalidOperationException: If an operation contains an invalid range.
        LabelConcurrentModificationException: If an update loses an optimistic-lock race.
    """
    q = (
        select(novel_models.ChapterContent.chapter_content_text)
        .select_from(models.LabelData)
        .where(models.LabelData.label_data_id == label_data_id)
        .join(
            novel_models.ChapterContent,
            novel_models.ChapterContent.chapter_content_id == models.LabelData.chapter_content_id,
        )
    )
    q = label_data_mod_access_select(q, current_user, label_edit_only=True)
    try:
        result = await db.execute(q)
        text = result.scalar_one()
    except NoResultFound as e:
        raise LabelDataNotFoundException from e
    except Exception:
        raise
    result = list()
    try:
        for op in request.ops:
            result.append(await apply_operation(db, current_user, label_data_id, text, op))
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e
    return result
