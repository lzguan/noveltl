"""
Service functions for labels.
"""

import logging
import uuid
from collections.abc import Sequence
from itertools import batched
from time import perf_counter

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from sqlalchemy import func, insert, literal, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DataError, IntegrityError, NoResultFound
from sqlalchemy.orm import Session

from ..auth.models import User
from ..autolabels import models as autolabel_models
from ..autolabels.constants import AutoLabelProgress
from ..exceptions import DataTooLongException, NotFoundException
from ..novels import models as novel_models
from ..novels.exceptions import ChapterContentNotFoundException, NovelNotFoundException
from ..novels.permissions import chapter_content_mod_access_select
from . import models, schemas
from .constants import LabelRole
from .exceptions import (
    LabelDataNotFoundException,
    LabelDataRevisionDuplicateException,
    LabelGroupNotFoundException,
    LabelWordMismatchInvalidOperationException,
)
from .permissions import (
    label_contributors_mod_access_select,
    label_data_mod_access_insert,
    label_data_mod_access_select,
    label_group_mod_access_insert,
    label_group_mod_access_select,
    label_group_mod_access_update,
)
from .utils import apply_operation

logger = logging.getLogger(__name__)

PROMOTION_CANDIDATE_BATCH_SIZE = 1000
PROMOTION_LABEL_BATCH_SIZE = 1000


def query_label_groups(db: Session, current_user: User, novel_id: uuid.UUID) -> Sequence[models.LabelGroup]:
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


def query_label_groups_with_contributor_info(
    db: Session, current_user: User, novel_id: uuid.UUID
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
    result = db.execute(q)
    result_rows = result.all()
    out: list[schemas.LabelGroupWithRole] = []
    for lg, r in result_rows:
        label_group: models.LabelGroup = lg
        role: LabelRole = r
        out.append(schemas.LabelGroupWithRole(label_group=label_group, role=role))

    return out


def query_label_group_by_id(db: Session, current_user: User, label_group_id: uuid.UUID) -> models.LabelGroup:
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


def query_label_datas(
    db: Session, current_user: User, label_group_id: uuid.UUID, start: int | None, end: int | None
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
    result = db.execute(q)
    result_rows = result.scalars().all()
    return result_rows


def query_label_data_by_id(db: Session, current_user: User, label_data_id: uuid.UUID) -> models.LabelData:
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
        result = db.execute(q)
        label_data = result.scalar_one()
    except NoResultFound as e:
        raise LabelDataNotFoundException from e
    return label_data


def query_labels_by_label_data_id(db: Session, current_user: User, label_data_id: uuid.UUID) -> Sequence[models.Label]:
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
    result = db.execute(q)
    result_rows = result.scalars().all()
    return result_rows


def query_label_contributors_of_label_group(
    db: Session, current_user: User, label_group_id: uuid.UUID
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
    result = db.execute(q)
    result_rows = result.scalars().all()
    if len(result_rows) == 0:
        raise LabelGroupNotFoundException
    return result_rows


def insert_label_group(db: Session, current_user: User, request: schemas.CreateLabelGroup) -> models.LabelGroup:
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
        result = db.execute(stmt)
        label_group = result.scalar_one()
        stmt = insert(models.LabelContributor).values(
            {
                "label_group_id": label_group.label_group_id,
                "user_id": current_user.user_id,
                "label_contributor_role": LabelRole.OWNER,
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
        raise
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise
    except NoResultFound as e:
        db.rollback()
        raise NovelNotFoundException from e
    except Exception:
        db.rollback()
        raise
    return label_group


def modify_label_group(
    db: Session, current_user: User, label_group_id: uuid.UUID, request: schemas.UpdateLabelGroup
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
        result = db.execute(stmt)
        label_group = result.scalar_one()
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise
    except NoResultFound as e:
        db.rollback()
        raise LabelGroupNotFoundException from e
    except Exception:
        db.rollback()
        raise
    return label_group


def insert_label_data(
    db: Session, current_user: User, label_group_id: uuid.UUID, request: schemas.CreateLabelData
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
        result = db.execute(stmt)
        label_data = result.scalar_one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise NotFoundException("Either chapter content or label group not found.") from e
            elif pgcode == errorcodes.UNIQUE_VIOLATION:
                raise LabelDataRevisionDuplicateException from e
        raise
    except NoResultFound as e:
        db.rollback()
        raise LabelGroupNotFoundException from e
    except Exception:
        db.rollback()
        raise
    return label_data


def modify_label_data_by_stream(
    db: Session, current_user: User, label_data_id: uuid.UUID, request: schemas.UpdateLabelDataStream
) -> None:
    """
    Processes a stream of label datas

    Args:
        db: Database being modified
        current_user: User performing the modification
        label_data_id: id of label data being modified

    Raises:
        ChapterContentNotFoundException: If the chapter content associated with the label data is not found.
        LabelOutOfBoundsInvalidOperationException: If an operation refers to positions outside the text bounds.
        LabelWordMismatchInvalidOperationException: If the word provided in an operation does not match the text at the specified positions.
        LabelDataNotFoundException: If the LabelData does not exist or the user lacks permissions.
        LabelExclusionViolationInvalidOperationException: If an add/update operation creates an overlapping label (exclusion constraint violation).
        LabelNotExistsInvalidOperationException: If a delete operation targets a label that does not exist.
        LabelInvalidOperationException: If an update operation is malformed (e.g. setting a new word without moving the label).
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
    q = chapter_content_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        text = result.scalar_one()
    except NoResultFound as e:
        raise ChapterContentNotFoundException from e
    except Exception:
        raise
    try:
        for op in request.ops:
            apply_operation(db, current_user, label_data_id, text, op)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e


def _insert_label_datas_by_autolabels(
    db: Session,
    label_group_id: uuid.UUID,
    autolabel_pairs: list[tuple[uuid.UUID, uuid.UUID]],
    success: list[tuple[uuid.UUID, uuid.UUID]],
    errors: list[tuple[uuid.UUID, uuid.UUID, str]],
) -> None:
    """
    Insert one bounded batch of autolabels into label datas and labels.

    Args:
        db: Database being used.
        label_group_id: id of label group to attach new label_datas to.
        autolabel_pairs: Pairs of (chapter_content_id, run_id) to process.
        success: Mutable accumulator of successful (chapter_id, chapter_content_id) pairs.
        errors: Mutable accumulator of (chapter_id, chapter_content_id, message) errors.

    If the optimistic insert violates a database constraint, it is recursively
    divided until the failing chapters can be reported individually. Each attempt
    uses a savepoint so a failed chapter never leaves behind an empty label data row.
    """
    q = (
        select(autolabel_models.AutoLabel, novel_models.ChapterContent)
        .select_from(autolabel_models.AutoLabel)
        .join(
            novel_models.ChapterContent,
            novel_models.ChapterContent.chapter_content_id == autolabel_models.AutoLabel.chapter_content_id,
        )
        .where(
            tuple_(autolabel_models.AutoLabel.chapter_content_id, autolabel_models.AutoLabel.run_id).in_(
                autolabel_pairs
            )
        )
    )
    candidates = db.execute(q).all()

    if len(candidates) != len(autolabel_pairs):
        raise RuntimeError("Autolabel promotion candidates changed during processing")

    valid_candidates: list[tuple[autolabel_models.AutoLabel, novel_models.ChapterContent]] = []
    for autolabel, chapter_content in candidates:
        try:
            if autolabel.auto_label_data and not all(
                chapter_content.chapter_content_text[label["label_start"] : label["label_end"]] == label["label_word"]
                for label in autolabel.auto_label_data
            ):
                raise LabelWordMismatchInvalidOperationException("Text mismatch between autolabel and chapter")
            sorted_labels = sorted(autolabel.auto_label_data or [], key=lambda label: label["label_start"])
            if any(
                current["label_start"] < previous["label_end"]
                for previous, current in zip(sorted_labels, sorted_labels[1:], strict=False)
            ):
                errors.append(
                    (
                        chapter_content.chapter_id,
                        autolabel.chapter_content_id,
                        f"Failed insert for chapter content with id {autolabel.chapter_content_id}, autolabel id {autolabel.auto_label_id} due to labels in autolabel data overlapping.",
                    )
                )
                continue
            valid_candidates.append((autolabel, chapter_content))
        except Exception as e:
            errors.append(
                (
                    chapter_content.chapter_id,
                    autolabel.chapter_content_id,
                    f"Failed insert for chapter content with id {autolabel.chapter_content_id}, autolabel id {autolabel.auto_label_id} due to unknown reason: {str(e)}",
                )
            )

    def append_database_error(
        autolabel: autolabel_models.AutoLabel,
        chapter_content: novel_models.ChapterContent,
        error: IntegrityError | DataError,
    ) -> None:
        if isinstance(error, IntegrityError) and isinstance(error.orig, PgError):
            if error.orig.pgcode == errorcodes.EXCLUSION_VIOLATION:
                reason = "labels in autolabel data overlapping"
            else:
                reason = f"unknown reason: {error.orig}"
        else:
            reason = f"unknown reason: {error}"
        errors.append(
            (
                chapter_content.chapter_id,
                autolabel.chapter_content_id,
                f"Failed insert for chapter content with id {autolabel.chapter_content_id}, autolabel id {autolabel.auto_label_id} due to {reason}.",
            )
        )

    def insert_candidate_batch(
        batch: list[tuple[autolabel_models.AutoLabel, novel_models.ChapterContent]],
    ) -> None:
        try:
            with db.begin_nested():
                label_data_stmt = (
                    pg_insert(models.LabelData)
                    .values(
                        [
                            {
                                "label_group_id": label_group_id,
                                "chapter_content_id": autolabel.chapter_content_id,
                            }
                            for autolabel, _ in batch
                        ]
                    )
                    .on_conflict_do_nothing(constraint="one_label_group_per_chapter")
                    .returning(models.LabelData.label_data_id, models.LabelData.chapter_content_id)
                )
                inserted_label_datas = {
                    chapter_content_id: label_data_id
                    for label_data_id, chapter_content_id in db.execute(label_data_stmt).all()
                }
                label_values = (
                    {
                        "label_entity_group": label.get("label_entity_group", "MISC"),
                        "label_score": label.get("label_score", 1.0),
                        "label_word": label["label_word"],
                        "label_start": label["label_start"],
                        "label_end": label["label_end"],
                        "label_dirty": label.get("label_dirty", True),
                        "label_data_id": inserted_label_datas[autolabel.chapter_content_id],
                    }
                    for autolabel, _ in batch
                    if autolabel.chapter_content_id in inserted_label_datas
                    for label in autolabel.auto_label_data or []
                )
                for label_batch in batched(label_values, PROMOTION_LABEL_BATCH_SIZE):
                    db.execute(insert(models.Label), list(label_batch))
        except (IntegrityError, DataError) as error:
            if len(batch) == 1:
                append_database_error(*batch[0], error)
                return
            midpoint = len(batch) // 2
            insert_candidate_batch(batch[:midpoint])
            insert_candidate_batch(batch[midpoint:])
            return

        for autolabel, chapter_content in batch:
            if autolabel.chapter_content_id in inserted_label_datas:
                success.append((chapter_content.chapter_id, autolabel.chapter_content_id))
            else:
                errors.append(
                    (
                        chapter_content.chapter_id,
                        autolabel.chapter_content_id,
                        f"Failed insert for chapter content with id {autolabel.chapter_content_id}, autolabel id {autolabel.auto_label_id} due to label data for label group already existing.",
                    )
                )

    if valid_candidates:
        insert_candidate_batch(valid_candidates)


def insert_label_datas_by_autolabels(
    db: Session, current_user: User, label_group_id: uuid.UUID, request: schemas.CreateLabelDataByAutoLabel
) -> schemas.CreateLabelDataByAutoLabelStatus:
    """
    Move matching autolabels into a label group in bounded batches.

    Candidate selection loads only identifiers for the complete request. Full
    chapter text and autolabel JSON are then queried and inserted in batches of
    at most ``PROMOTION_CANDIDATE_BATCH_SIZE``.
    """
    promotion_started = perf_counter()
    log_context = f"run_id={request.run_id} label_group_id={label_group_id}"
    q = (
        select(
            autolabel_models.AutoLabel.chapter_content_id,
            autolabel_models.AutoLabel.run_id,
            autolabel_models.AutoLabel.auto_label_id,
            novel_models.Chapter.chapter_id,
        )
        .select_from(autolabel_models.AutoLabel)
        .join(models.LabelGroup, models.LabelGroup.label_group_id == label_group_id)
        .join(
            autolabel_models.AutoLabelRun,
            autolabel_models.AutoLabelRun.run_id == autolabel_models.AutoLabel.run_id,
        )
        .join(
            novel_models.ChapterContent,
            novel_models.ChapterContent.chapter_content_id == autolabel_models.AutoLabel.chapter_content_id,
        )
        .join(novel_models.Chapter, novel_models.Chapter.chapter_id == novel_models.ChapterContent.chapter_id)
        .where(autolabel_models.AutoLabel.run_id == request.run_id)
        .where(autolabel_models.AutoLabel.auto_label_status == AutoLabelProgress.DONE)
        .where(autolabel_models.AutoLabelRun.novel_id == models.LabelGroup.novel_id)
        .where(novel_models.Chapter.novel_id == autolabel_models.AutoLabelRun.novel_id)
        .where(
            novel_models.ChapterContent.chapter_content_version
            == select(func.max(novel_models.ChapterContent.chapter_content_version))
            .where(novel_models.ChapterContent.chapter_id == novel_models.Chapter.chapter_id)
            .correlate(novel_models.Chapter)
            .scalar_subquery()
        )
        .order_by(novel_models.Chapter.chapter_num)
    )
    q = label_group_mod_access_select(q, current_user)
    if request.chapter_ids is not None and len(request.chapter_ids) > 0:
        q = q.where(novel_models.Chapter.chapter_id.in_(request.chapter_ids))
    if request.start is not None:
        q = q.where(novel_models.Chapter.chapter_num >= request.start)
    if request.end is not None:
        q = q.where(novel_models.Chapter.chapter_num < request.end)

    candidate_identifiers = db.execute(q).all()

    success: list[tuple[uuid.UUID, uuid.UUID]] = []
    errors: list[tuple[uuid.UUID, uuid.UUID, str]] = []

    if not candidate_identifiers:
        logger.info(
            "Autolabel promotion ended %s success_count=0 error_count=0 elapsed_ms=%.2f",
            log_context,
            (perf_counter() - promotion_started) * 1000,
        )
        return schemas.CreateLabelDataByAutoLabelStatus(success=success, errors=errors)

    permission_q = label_data_mod_access_insert(select(literal(1)), current_user, label_group_id)
    try:
        db.execute(permission_q).scalar_one()
    except NoResultFound:
        for chapter_content_id, _, auto_label_id, chapter_id in candidate_identifiers:
            errors.append(
                (
                    chapter_id,
                    chapter_content_id,
                    f"Failed insert for chapter content with id {chapter_content_id}, autolabel id {auto_label_id} due to insufficient permissions.",
                )
            )
        logger.info(
            "Autolabel promotion ended %s success_count=0 error_count=%s elapsed_ms=%.2f",
            log_context,
            len(errors),
            (perf_counter() - promotion_started) * 1000,
        )
        return schemas.CreateLabelDataByAutoLabelStatus(success=success, errors=errors)

    autolabel_pairs = [(chapter_content_id, run_id) for chapter_content_id, run_id, _, _ in candidate_identifiers]
    for autolabel_batch in batched(autolabel_pairs, PROMOTION_CANDIDATE_BATCH_SIZE):
        _insert_label_datas_by_autolabels(
            db,
            label_group_id,
            list(autolabel_batch),
            success,
            errors,
        )

    db.commit()
    logger.info(
        "Autolabel promotion ended %s success_count=%s error_count=%s elapsed_ms=%.2f",
        log_context,
        len(success),
        len(errors),
        (perf_counter() - promotion_started) * 1000,
    )
    return schemas.CreateLabelDataByAutoLabelStatus(success=success, errors=errors)
