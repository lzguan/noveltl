"""
Promotion of autolabel runs into label groups.
"""

import logging
import uuid
from itertools import batched
from time import perf_counter

from psycopg.errors import ExclusionViolation
from sqlalchemy import func, insert, literal, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DataError, IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.autolabels import models as autolabel_models
from src.autolabels import schemas
from src.autolabels.constants import AutoLabelProgress
from src.labels import models as label_models
from src.labels.exceptions import LabelGroupNotFoundException, LabelWordMismatchInvalidOperationException
from src.labels.permissions import label_data_mod_access_insert, label_group_mod_access_select
from src.novels import models as novel_models

logger = logging.getLogger(__name__)

PROMOTION_CANDIDATE_BATCH_SIZE = 1000
PROMOTION_LABEL_BATCH_SIZE = 1000


async def _insert_label_datas_by_autolabels(
    db: AsyncSession,
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
    if not autolabel_pairs:
        return

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
    candidates = (await db.execute(q)).all()

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
        if isinstance(error, IntegrityError) and isinstance(error.orig, ExclusionViolation):
            reason = "labels in autolabel data overlapping"
        elif isinstance(error, IntegrityError):
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

    async def insert_candidate_batch(
        batch: list[tuple[autolabel_models.AutoLabel, novel_models.ChapterContent]],
    ) -> None:
        try:
            async with db.begin_nested():
                label_data_stmt = (
                    pg_insert(label_models.LabelData)
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
                )
                await db.execute(label_data_stmt)
                chapter_content_ids = [autolabel.chapter_content_id for autolabel, _ in batch]
                label_datas = {
                    chapter_content_id: label_data_id
                    for label_data_id, chapter_content_id in (
                        await db.execute(
                            select(label_models.LabelData.label_data_id, label_models.LabelData.chapter_content_id)
                            .where(label_models.LabelData.label_group_id == label_group_id)
                            .where(label_models.LabelData.chapter_content_id.in_(chapter_content_ids))
                        )
                    ).all()
                }
                if len(label_datas) != len(batch):
                    raise RuntimeError("Label datas changed during autolabel promotion")
                label_values = (
                    {
                        "label_entity_group": label.get("label_entity_group", "MISC"),
                        "label_score": label.get("label_score", 1.0),
                        "label_word": label["label_word"],
                        "label_start": label["label_start"],
                        "label_end": label["label_end"],
                        "label_dirty": label.get("label_dirty", True),
                        "label_data_id": label_datas[autolabel.chapter_content_id],
                    }
                    for autolabel, _ in batch
                    for label in autolabel.auto_label_data or []
                )
                for label_batch in batched(label_values, PROMOTION_LABEL_BATCH_SIZE, strict=False):
                    await db.execute(insert(label_models.Label), list(label_batch))
        except (IntegrityError, DataError) as error:
            if len(batch) == 1:
                append_database_error(*batch[0], error)
                return
            # TODO: Consider a higher split factor to reduce repeated work when isolating rare database failures.
            midpoint = len(batch) // 2
            await insert_candidate_batch(batch[:midpoint])
            await insert_candidate_batch(batch[midpoint:])
            return

        for autolabel, chapter_content in batch:
            success.append((chapter_content.chapter_id, autolabel.chapter_content_id))

    if valid_candidates:
        await insert_candidate_batch(valid_candidates)


async def insert_label_datas_by_autolabels(
    db: AsyncSession, current_user: User, label_group_id: uuid.UUID, request: schemas.CreateLabelDataByAutoLabel
) -> schemas.CreateLabelDataByAutoLabelStatus:
    """
    Move matching autolabels into a label group in bounded batches.

    Candidate selection loads only identifiers for the complete request. Full
    chapter text and autolabel JSON are then queried and inserted in batches of
    at most ``PROMOTION_CANDIDATE_BATCH_SIZE``.
    """
    promotion_started = perf_counter()
    log_context = f"run_id={request.run_id} label_group_id={label_group_id}"

    # Promotion writes into the target group, so viewers must be rejected
    # before candidate identifiers are loaded.
    permission_query = label_group_mod_access_select(
        select(label_models.LabelGroup.label_group_id).where(label_models.LabelGroup.label_group_id == label_group_id),
        current_user,
        label_edit_only=True,
    )
    if (await db.execute(permission_query)).scalar_one_or_none() is None:
        raise LabelGroupNotFoundException(f"Label group with ID {label_group_id} not found or not accessible.")

    q = (
        select(
            autolabel_models.AutoLabel.chapter_content_id,
            autolabel_models.AutoLabel.run_id,
            autolabel_models.AutoLabel.auto_label_id,
            novel_models.Chapter.chapter_id,
        )
        .select_from(autolabel_models.AutoLabel)
        .join(label_models.LabelGroup, label_models.LabelGroup.label_group_id == label_group_id)
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
        .where(autolabel_models.AutoLabelRun.novel_id == label_models.LabelGroup.novel_id)
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
    q = label_group_mod_access_select(q, current_user, label_edit_only=True)
    if request.chapter_ids is not None and len(request.chapter_ids) > 0:
        q = q.where(novel_models.Chapter.chapter_id.in_(request.chapter_ids))
    if request.start is not None:
        q = q.where(novel_models.Chapter.chapter_num >= request.start)
    if request.end is not None:
        q = q.where(novel_models.Chapter.chapter_num < request.end)

    candidate_identifiers = (await db.execute(q)).all()

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
        (await db.execute(permission_q)).scalar_one()
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
    for autolabel_batch in batched(autolabel_pairs, PROMOTION_CANDIDATE_BATCH_SIZE, strict=False):
        await _insert_label_datas_by_autolabels(
            db,
            label_group_id,
            list(autolabel_batch),
            success,
            errors,
        )

    await db.commit()
    logger.info(
        "Autolabel promotion ended %s success_count=%s error_count=%s elapsed_ms=%.2f",
        log_context,
        len(success),
        len(errors),
        (perf_counter() - promotion_started) * 1000,
    )
    return schemas.CreateLabelDataByAutoLabelStatus(success=success, errors=errors)
