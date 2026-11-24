"""
Promotion of autolabel runs into label groups.
"""

import logging
import uuid
from datetime import timedelta
from itertools import batched, pairwise
from time import perf_counter
from typing import Literal

from psycopg.errors import ExclusionViolation
from sqlalchemy import (
    Boolean,
    Float,
    Integer,
    String,
    and_,
    column,
    func,
    insert,
    literal,
    or_,
    select,
    true,
    tuple_,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DataError, IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.auth.models import User
from src.autolabels import models as autolabel_models
from src.autolabels import schemas
from src.autolabels.constants import AutoLabelProgress, PromotionItemOutcome
from src.labels import models as label_models
from src.labels.constants import MAX_LABEL_ENTITY_GROUP_NAME_LEN, MAX_LABEL_WORD_LEN
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
        edit_only=True,
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
    q = label_group_mod_access_select(q, current_user, edit_only=True)
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


PROMOTION_ITEM_BATCH_SIZE = 200
PROMOTION_CLAIM_DURATION = timedelta(minutes=2)

_Outcome = tuple[Literal[PromotionItemOutcome.DONE], None] | tuple[Literal[PromotionItemOutcome.FAILED], str]
aliased_content = aliased(novel_models.ChapterContent)


class PromotionClaimLostError(Exception):
    pass


async def claim_promotion_job(
    db: AsyncSession, promotion_id: uuid.UUID, claim_token: uuid.UUID, claim_duration: timedelta
) -> autolabel_models.LabelPromotionJob | None:
    claim = (
        update(autolabel_models.LabelPromotionJob)
        .where(
            autolabel_models.LabelPromotionJob.promotion_id == promotion_id,
            or_(
                autolabel_models.LabelPromotionJob.status == AutoLabelProgress.PENDING,
                and_(
                    autolabel_models.LabelPromotionJob.status == AutoLabelProgress.PROCESSING,
                    autolabel_models.LabelPromotionJob.claim_expires_at < func.now(),
                ),
            ),
        )
        .values(
            status=AutoLabelProgress.PROCESSING,
            claim_token=claim_token,
            claim_expires_at=func.now() + claim_duration,
        )
        .returning(autolabel_models.LabelPromotionJob)
    )
    try:
        job = (await db.execute(claim)).scalar_one_or_none()
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return job


async def _check_items(
    db: AsyncSession, auto_label_ids: list[uuid.UUID]
) -> tuple[list[uuid.UUID], dict[uuid.UUID, _Outcome]]:
    latest_version = (
        select(func.max(novel_models.ChapterContent.chapter_content_version))
        .where(novel_models.ChapterContent.chapter_id == aliased_content.chapter_id)
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(
                autolabel_models.AutoLabel.auto_label_id,
                autolabel_models.AutoLabel.auto_label_data,
                aliased_content.chapter_content_text,
                aliased_content.chapter_content_version == latest_version,
            )
            .join(aliased_content, aliased_content.chapter_content_id == autolabel_models.AutoLabel.chapter_content_id)
            .where(autolabel_models.AutoLabel.auto_label_id.in_(auto_label_ids))
        )
    ).all()
    valid: list[uuid.UUID] = []
    outcomes: dict[uuid.UUID, _Outcome] = {}
    for auto_label_id, labels, text, is_latest in rows:
        problem = (
            "The chapter changed after the promotion was requested."
            if not is_latest
            else _label_problem(text, labels if labels is not None else [])
        )
        if problem is None:
            valid.append(auto_label_id)
        else:
            outcomes[auto_label_id] = (PromotionItemOutcome.FAILED, problem)
    return valid, outcomes


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# Checks everything the labels table constraints would reject, so a batch insert only
# fails (and is bisected) for causes not anticipated here.
def _label_problem(text: str, labels: object) -> str | None:
    if not isinstance(labels, list) or not all(isinstance(label, dict) for label in labels):
        return "The autolabel data is not a list of labels."
    for label in labels:
        word, start, end = label.get("label_word"), label.get("label_start"), label.get("label_end")
        group, score, dirty = label.get("label_entity_group"), label.get("label_score"), label.get("label_dirty")
        if not isinstance(word, str) or not _is_int(start) or not _is_int(end):
            return "A label is missing its word, start or end."
        if not 0 <= start < end <= len(text):
            return "A label's span is empty or outside the chapter text."
        if len(word) > MAX_LABEL_WORD_LEN:
            return f"A label's word is longer than {MAX_LABEL_WORD_LEN} characters."
        if group is not None and (not isinstance(group, str) or len(group) > MAX_LABEL_ENTITY_GROUP_NAME_LEN):
            return f"A label's entity group is not text of at most {MAX_LABEL_ENTITY_GROUP_NAME_LEN} characters."
        if score is not None and (isinstance(score, bool) or not isinstance(score, int | float) or not 0 <= score <= 1):
            return "A label's score is not a number between 0 and 1."
        if dirty is not None and not isinstance(dirty, bool):
            return "A label's dirty flag is not a boolean."
        if text[start:end] != word:
            return "Text mismatch between autolabel and chapter."
    if _overlaps(labels):
        return "Labels in the autolabel data overlap."
    return None


def _overlaps(labels: list[dict]) -> bool:
    ordered = sorted(labels, key=lambda label: label["label_start"])
    return any(current["label_start"] < previous["label_end"] for previous, current in pairwise(ordered))


def _ensure_label_datas_statement(label_group_id: uuid.UUID, auto_label_ids: list[uuid.UUID]):
    autolabel = autolabel_models.AutoLabel
    return (
        pg_insert(label_models.LabelData)
        .from_select(
            ["label_group_id", "chapter_content_id"],
            select(literal(label_group_id), autolabel.chapter_content_id).where(
                autolabel.auto_label_id.in_(auto_label_ids)
            ),
        )
        .on_conflict_do_nothing(constraint="one_label_group_per_chapter")
    )


def _promotion_statement(label_group_id: uuid.UUID, auto_label_ids: list[uuid.UUID], *, skip_existing_labels: bool):
    autolabel = autolabel_models.AutoLabel
    label_data = label_models.LabelData
    existing_label = aliased(label_models.Label)

    target_query = (
        select(
            autolabel.auto_label_id,
            label_data.label_data_id,
            autolabel.auto_label_data,
        )
        .join(
            label_data,
            and_(
                label_data.label_group_id == label_group_id,
                label_data.chapter_content_id == autolabel.chapter_content_id,
            ),
        )
        .where(autolabel.auto_label_id.in_(auto_label_ids))
    )
    if skip_existing_labels:
        has_existing_labels = (
            select(existing_label.label_id).where(existing_label.label_data_id == label_data.label_data_id).exists()
        )
        target_query = target_query.where(~has_existing_labels)
    target_label_datas = target_query.cte("target_label_datas")

    labels = (
        func.jsonb_to_recordset(target_label_datas.c.auto_label_data)
        .table_valued(
            column("label_word", String),
            column("label_start", Integer),
            column("label_end", Integer),
            column("label_entity_group", String),
            column("label_score", Float),
            column("label_dirty", Boolean),
        )
        .render_derived(name="l", with_types=True)
    )
    label_rows = (
        select(
            target_label_datas.c.label_data_id,
            labels.c.label_word,
            labels.c.label_start,
            labels.c.label_end,
            func.coalesce(labels.c.label_entity_group, "MISC"),
            func.coalesce(labels.c.label_score, 1.0),
            func.coalesce(labels.c.label_dirty, true()),
        )
        .select_from(target_label_datas)
        .join(labels, true())
    )
    if not skip_existing_labels:
        overlapping_existing = (
            select(existing_label.label_id)
            .where(
                existing_label.label_data_id == target_label_datas.c.label_data_id,
                func.int4range(existing_label.label_start, existing_label.label_end, "[)").op("&&")(
                    func.int4range(labels.c.label_start, labels.c.label_end, "[)")
                ),
            )
            .exists()
        )
        label_rows = label_rows.where(~overlapping_existing)
    new_labels = (
        insert(label_models.Label)
        .from_select(
            [
                "label_data_id",
                "label_word",
                "label_start",
                "label_end",
                "label_entity_group",
                "label_score",
                "label_dirty",
            ],
            label_rows,
        )
        .cte("new_labels")
    )
    return select(target_label_datas.c.auto_label_id).add_cte(new_labels)


async def _insert_items(
    db: AsyncSession,
    label_group_id: uuid.UUID,
    batch: list[uuid.UUID],
    outcomes: dict[uuid.UUID, _Outcome],
    *,
    skip_existing_labels: bool,
) -> None:
    try:
        async with db.begin_nested():
            await db.execute(_ensure_label_datas_statement(label_group_id, batch))
            statement = _promotion_statement(label_group_id, batch, skip_existing_labels=skip_existing_labels)
            promoted = set((await db.execute(statement)).scalars())
    except (IntegrityError, DataError) as error:
        if len(batch) == 1:
            reason = (
                "Labels in the autolabel data overlap."
                if isinstance(error, IntegrityError) and isinstance(error.orig, ExclusionViolation)
                else f"The labels could not be inserted: {error.orig}"
            )
            outcomes[batch[0]] = (PromotionItemOutcome.FAILED, reason)
            return
        midpoint = len(batch) // 2
        await _insert_items(db, label_group_id, batch[:midpoint], outcomes, skip_existing_labels=skip_existing_labels)
        await _insert_items(db, label_group_id, batch[midpoint:], outcomes, skip_existing_labels=skip_existing_labels)
        return
    for auto_label_id in batch:
        if auto_label_id in promoted:
            outcomes[auto_label_id] = (PromotionItemOutcome.DONE, None)
        else:
            outcomes[auto_label_id] = (
                PromotionItemOutcome.FAILED,
                "The chapter already has labels in this label group.",
            )


async def _renew_claim(
    db: AsyncSession,
    promotion_id: uuid.UUID,
    claim_token: uuid.UUID,
    claim_duration: timedelta,
    *,
    status: AutoLabelProgress | None = None,
) -> None:
    renew = (
        update(autolabel_models.LabelPromotionJob)
        .where(
            autolabel_models.LabelPromotionJob.promotion_id == promotion_id,
            autolabel_models.LabelPromotionJob.claim_token == claim_token,
        )
        .values(claim_expires_at=func.now() + claim_duration)
        .returning(autolabel_models.LabelPromotionJob.promotion_id)
    )
    if status is not None:
        renew = renew.values(status=status)
    renewed = await db.execute(renew)
    if renewed.scalar_one_or_none() is None:
        raise PromotionClaimLostError(f"Promotion {promotion_id} is no longer claimed by this worker")


async def process_promotion_job(
    db: AsyncSession,
    promotion_id: uuid.UUID,
    *,
    claim_duration: timedelta = PROMOTION_CLAIM_DURATION,
    batch_size: int = PROMOTION_ITEM_BATCH_SIZE,
) -> bool:
    # Each batch commits its labels, item outcomes and renewed claim together, so an interrupted
    # job resumes from its first unprocessed item. Returns False if the job was not claimable.
    claim_token = uuid.uuid4()
    job = await claim_promotion_job(db, promotion_id, claim_token, claim_duration)
    if job is None:
        return False
    label_group_id = job.label_group_id
    skip_existing_labels = job.skip_existing_labels
    started = perf_counter()
    item = autolabel_models.LabelPromotionJobItem
    try:
        while True:
            auto_label_ids = list(
                (
                    await db.execute(
                        select(item.auto_label_id)
                        .where(item.promotion_id == promotion_id, item.outcome.is_(None))
                        .order_by(item.position)
                        .limit(batch_size)
                    )
                ).scalars()
            )
            if not auto_label_ids:
                break
            valid, outcomes = await _check_items(db, auto_label_ids)
            for missing in set(auto_label_ids) - set(valid) - outcomes.keys():
                outcomes[missing] = (PromotionItemOutcome.FAILED, "The autolabel no longer exists.")
            if valid:
                await _insert_items(db, label_group_id, valid, outcomes, skip_existing_labels=skip_existing_labels)
            await db.execute(
                update(item),
                [
                    {
                        "promotion_id": promotion_id,
                        "auto_label_id": auto_label_id,
                        "outcome": outcome,
                        "message": message,
                    }
                    for auto_label_id, (outcome, message) in outcomes.items()
                ],
            )
            await _renew_claim(db, promotion_id, claim_token, claim_duration)
            await db.commit()
        await _renew_claim(db, promotion_id, claim_token, claim_duration, status=AutoLabelProgress.DONE)
        await db.execute(
            update(autolabel_models.LabelPromotionJob)
            .where(autolabel_models.LabelPromotionJob.promotion_id == promotion_id)
            .values(claim_token=None, claim_expires_at=None)
        )
        await db.commit()
    except PromotionClaimLostError:
        await db.rollback()
        raise
    except Exception as error:
        await db.rollback()
        await db.execute(
            update(autolabel_models.LabelPromotionJob)
            .where(
                autolabel_models.LabelPromotionJob.promotion_id == promotion_id,
                autolabel_models.LabelPromotionJob.claim_token == claim_token,
            )
            .values(
                status=AutoLabelProgress.FAILED,
                message=f"Promotion failed: {error}",
                claim_token=None,
                claim_expires_at=None,
            )
        )
        await db.commit()
        raise
    logger.info(
        "Label promotion finished promotion_id=%s elapsed_ms=%.2f", promotion_id, (perf_counter() - started) * 1000
    )
    return True
