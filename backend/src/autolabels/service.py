"""
Service functions for auto labeling.
"""

import asyncio
import logging
import uuid
from uuid import uuid4

from psycopg.errors import UniqueViolation
from sqlalchemy import and_, exists, func, insert, literal, select
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from src.auth.models import User
from src.autolabels import models, schemas
from src.autolabels.constants import AutoLabelProgress, PromotionItemOutcome
from src.autolabels.exceptions import (
    AutoLabelDuplicateException,
    AutoLabelNotFoundException,
    EnqueueFailedException,
    PromotionAlreadyActiveException,
)
from src.autolabels.inference.dispatch.dispatcher import AutoLabelDispatcher
from src.autolabels.permissions import auto_label_mod_access_insert, auto_label_mod_access_select
from src.autolabels.promotions.dispatch.dispatcher import PromotionDispatcher
from src.autolabels.schemas import CreateLabelDataByAutoLabel
from src.labels.exceptions import LabelGroupNotFoundException
from src.labels.models import LabelData, LabelGroup
from src.labels.permissions import label_group_mod_access_select
from src.novels import models as nm
from src.novels.exceptions import NovelNotFoundException
from src.novels.permissions import chapter_mod_access_select, novel_mod_access_select

logger = logging.getLogger(__name__)


async def query_auto_label_runs(
    db: AsyncSession,
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
    subq = select(1).select_from(nm.Novel).where(nm.Novel.novel_id == novel_id)
    subq = novel_mod_access_select(subq, current_user)
    q = q.where(exists(subq))
    result = await db.execute(q)
    rows = result.scalars().all()
    return [schemas.AutoLabelRun.model_validate(row) for row in rows]


async def query_auto_labels_by_run(
    db: AsyncSession,
    current_user: User,
    run_id: uuid.UUID,
    start: int | None = None,
    end: int | None = None,
) -> list[schemas.AutoLabelMetaWithCid]:
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
        (
            select(models.AutoLabel, nm.Chapter.chapter_id)
            .options(defer(models.AutoLabel.auto_label_data))
            .where(models.AutoLabel.run_id == run_id)
        )
        .join(
            nm.ChapterContent,
            nm.ChapterContent.chapter_content_id == models.AutoLabel.chapter_content_id,
        )
        .join(nm.Chapter, nm.Chapter.chapter_id == nm.ChapterContent.chapter_id)
    )
    if start is not None or end is not None:
        if start is not None:
            q = q.where(nm.Chapter.chapter_num >= start)
        if end is not None:
            q = q.where(nm.Chapter.chapter_num < end)
    q = auto_label_mod_access_select(q, current_user)
    result = await db.execute(q)
    rows = result.all()

    ret = []
    for alm, cid in rows:
        auto_label_meta = schemas.AutoLabelMeta.model_validate(alm)
        chapter_id: uuid.UUID = cid
        ret.append(schemas.AutoLabelMetaWithCid(auto_label_meta=auto_label_meta, chapter_id=chapter_id))
    return ret


async def query_auto_label_by_id(db: AsyncSession, current_user: User, auto_label_id: uuid.UUID) -> models.AutoLabel:
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
        result = await db.execute(q)
        autolabel = result.scalar_one()
    except NoResultFound as e:
        raise AutoLabelNotFoundException from e
    return autolabel


async def insert_auto_labels(
    db: AsyncSession,
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
    logger.info(
        "Creating autolabel run novel_id=%s user_id=%s model_name=%s start=%s end=%s is_public=%s chapter_ids=%s",
        request.novel_id,
        current_user.user_id,
        model_name,
        request.start,
        request.end,
        request.is_public,
        len(request.chapter_ids) if request.chapter_ids else 0,
    )

    # Starting inference requires membership in the novel, but viewers are
    # intentionally allowed alongside editors and owners.
    permission_query = (
        select(literal(1))
        .select_from(nm.ChapterContent)
        .join(nm.Chapter, nm.Chapter.chapter_id == nm.ChapterContent.chapter_id)
        .where(nm.Chapter.novel_id == request.novel_id)
        .limit(1)
    )
    permission_query = auto_label_mod_access_insert(
        permission_query,
        current_user,
        contributor_only=True,
    )
    if (await db.execute(permission_query)).scalar_one_or_none() is None:
        raise NovelNotFoundException(f"Novel with ID {request.novel_id} not found or not accessible.")

    # 1. Create the run.
    run = models.AutoLabelRun(
        novel_id=request.novel_id,
        triggered_by=current_user.user_id,
        model_name=model_name,
        model_params=model_params_dump,
    )
    db.add(run)
    # Flush to get the server-generated run_id before we insert autolabels.
    await db.flush()
    run_id = run.run_id
    logger.info(
        "Autolabel run created run_id=%s novel_id=%s model_name=%s",
        run_id,
        request.novel_id,
        model_name,
    )

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
            nm.ChapterContent.chapter_content_id,
            literal(run_id),
        )
        .select_from(nm.ChapterContent)
        .join(nm.Chapter, nm.Chapter.chapter_id == nm.ChapterContent.chapter_id)
        .join(nm.Novel, nm.Novel.novel_id == nm.Chapter.novel_id)
        .where(nm.Chapter.novel_id == request.novel_id)
        .where(
            nm.ChapterContent.chapter_content_version
            == select(func.max(nm.ChapterContent.chapter_content_version))
            .where(nm.ChapterContent.chapter_id == nm.Chapter.chapter_id)
            .correlate(nm.Chapter)
            .scalar_subquery()
        )
    )
    if request.chapter_ids:
        q = q.where(nm.Chapter.chapter_id.in_(request.chapter_ids))
    if request.start is not None:
        q = q.where(nm.Chapter.chapter_num >= request.start)
    if request.end is not None:
        q = q.where(nm.Chapter.chapter_num < request.end)
    if request.is_public is not None:
        q = q.where(nm.Chapter.chapter_is_public == request.is_public)
    q = auto_label_mod_access_insert(q, current_user, contributor_only=True)
    stmt = insert(models.AutoLabel).from_select(columns, q).returning(models.AutoLabel)
    try:
        result = await db.execute(stmt)
        result_rows = result.scalars().all()
        await db.commit()
        logger.info(
            "Autolabel rows inserted run_id=%s count=%s",
            run_id,
            len(result_rows),
        )
        if len(result_rows) == 0:
            logger.warning(
                "Autolabel run has no matching chapter contents run_id=%s novel_id=%s",
                run_id,
                request.novel_id,
            )
    except IntegrityError as e:
        await db.rollback()
        logger.exception("Autolabel insert integrity error run_id=%s novel_id=%s", run_id, request.novel_id)
        if isinstance(e.orig, UniqueViolation):
            raise AutoLabelDuplicateException from e
        raise
    except Exception:
        await db.rollback()
        logger.exception("Autolabel insert failed run_id=%s novel_id=%s", run_id, request.novel_id)
        raise

    # 3. Dispatch worker tasks.
    jobs: list[tuple[uuid.UUID, uuid.UUID]] = []
    for autolabel in result_rows:
        job_id = uuid4()
        autolabel.auto_label_last_job_id = job_id
        logger.info(
            "Autolabel job assigned run_id=%s auto_label_id=%s job_id=%s",
            run_id,
            autolabel.auto_label_id,
            job_id,
        )
        jobs.append((job_id, autolabel.auto_label_id))
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Autolabel job id commit failed run_id=%s", run_id)
        raise

    ret = await asyncio.gather(
        *(dispatcher.aenqueue(job_id, auto_label_id) for job_id, auto_label_id in jobs), return_exceptions=True
    )

    queued_count = 0
    failed_count = 0
    for i, result in enumerate(ret):
        autolabel = result_rows[i]
        if result is None:
            autolabel.auto_label_message = "Job queued."
            queued_count += 1
            logger.info(
                "Autolabel job queued run_id=%s auto_label_id=%s job_id=%s",
                run_id,
                autolabel.auto_label_id,
                autolabel.auto_label_last_job_id,
            )
        else:
            autolabel.auto_label_message = "Job failed to queue."
            autolabel.auto_label_status = AutoLabelProgress.FAILED
            failed_count += 1
            logger.error(
                "Autolabel job failed to queue run_id=%s auto_label_id=%s job_id=%s error=%s",
                run_id,
                autolabel.auto_label_id,
                autolabel.auto_label_last_job_id,
                result,
            )
    try:
        await db.commit()
        logger.info(
            "Autolabel queue dispatch completed run_id=%s queued=%s failed=%s",
            run_id,
            queued_count,
            failed_count,
        )
    except Exception:
        await db.rollback()
        logger.exception("Autolabel queue status commit failed run_id=%s", run_id)
        raise

    # 4. Build response.
    q = (
        select(models.AutoLabel.auto_label_id, nm.Chapter.chapter_id)
        .select_from(models.AutoLabel)
        .where(models.AutoLabel.run_id == run_id)
        .join(nm.ChapterContent, nm.ChapterContent.chapter_content_id == models.AutoLabel.chapter_content_id)
        .join(nm.Chapter, nm.Chapter.chapter_id == nm.ChapterContent.chapter_id)
    )
    q = auto_label_mod_access_select(q, current_user)
    q = chapter_mod_access_select(q, current_user)
    new_result_rows = (await db.execute(q)).all()
    alcid_map: dict[uuid.UUID, uuid.UUID] = {row[0]: row[1] for row in new_result_rows}

    run_schema = schemas.AutoLabelRun.model_validate(run)
    autolabel_schemas = [
        schemas.AutoLabelMetaWithCid(
            auto_label_meta=schemas.AutoLabelMeta.model_validate(al), chapter_id=alcid_map[al.auto_label_id]
        )
        for al in result_rows
    ]
    return schemas.CreateAutoLabelsResponse(run=run_schema, autolabels=autolabel_schemas)


def regenerate_auto_labels():
    pass


_ACTIVE = (AutoLabelProgress.PENDING, AutoLabelProgress.PROCESSING)


def _promotion_candidates(promotion_id: uuid.UUID, label_group_id: uuid.UUID, request: CreateLabelDataByAutoLabel):
    group_novel = select(LabelGroup.novel_id).where(LabelGroup.label_group_id == label_group_id).scalar_subquery()
    latest_version = (
        select(func.max(nm.ChapterContent.chapter_content_version))
        .where(nm.ChapterContent.chapter_id == nm.Chapter.chapter_id)
        .correlate(nm.Chapter)
        .scalar_subquery()
    )
    already_labelled = (
        select(LabelData.label_data_id)
        .where(
            LabelData.label_group_id == label_group_id,
            LabelData.chapter_content_id == models.AutoLabel.chapter_content_id,
        )
        .exists()
    )
    candidates = (
        select(
            literal(promotion_id),
            models.AutoLabel.auto_label_id,
            func.row_number().over(order_by=nm.Chapter.chapter_num) - 1,
        )
        .join(nm.ChapterContent, nm.ChapterContent.chapter_content_id == models.AutoLabel.chapter_content_id)
        .join(nm.Chapter, nm.Chapter.chapter_id == nm.ChapterContent.chapter_id)
        .where(
            models.AutoLabel.run_id == request.run_id,
            models.AutoLabel.auto_label_status == AutoLabelProgress.DONE,
            nm.Chapter.novel_id == group_novel,
            nm.ChapterContent.chapter_content_version == latest_version,
            ~already_labelled,
        )
    )
    if request.chapter_ids:
        candidates = candidates.where(nm.Chapter.chapter_id.in_(request.chapter_ids))
    if request.start is not None:
        candidates = candidates.where(nm.Chapter.chapter_num >= request.start)
    if request.end is not None:
        candidates = candidates.where(nm.Chapter.chapter_num < request.end)
    return (
        insert(models.LabelPromotionJobItem)
        .from_select(["promotion_id", "auto_label_id", "position"], candidates)
        .returning(models.LabelPromotionJobItem.position)
    )


async def create_promotion_job(
    db: AsyncSession,
    current_user: User,
    dispatcher: PromotionDispatcher,
    label_group_id: uuid.UUID,
    request: CreateLabelDataByAutoLabel,
) -> schemas.CreatedLabelPromotion:
    # The job row is selected from the label group the user can edit, joined to the run on the
    # same novel, so a missing group, a missing run and missing permission all insert nothing.
    job_values = select(
        literal(request.run_id),
        LabelGroup.label_group_id,
        literal(current_user.user_id),
    ).join(
        models.AutoLabelRun,
        and_(models.AutoLabelRun.run_id == request.run_id, models.AutoLabelRun.novel_id == LabelGroup.novel_id),
    )
    job_values = label_group_mod_access_select(
        job_values.where(LabelGroup.label_group_id == label_group_id), current_user, label_edit_only=True
    )
    try:
        created = (
            await db.execute(
                insert(models.LabelPromotionJob)
                .from_select(
                    ["run_id", "label_group_id", "requested_by"],
                    job_values,
                )
                .returning(models.LabelPromotionJob.promotion_id)
            )
        ).scalar_one_or_none()
        if created is None:
            raise LabelGroupNotFoundException(
                f"Label group {label_group_id} or autolabel run {request.run_id} not found or not editable."
            )
        promotion_id = created
        item_count = len((await db.execute(_promotion_candidates(promotion_id, label_group_id, request))).all())
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, UniqueViolation):
            raise PromotionAlreadyActiveException(
                "A promotion for this run and label group is still running."
            ) from error
        raise
    try:
        await dispatcher.aenqueue(promotion_id)
    except EnqueueFailedException:
        logger.warning("Label promotion enqueue failed; job left pending promotion_id=%s", promotion_id)
    return schemas.CreatedLabelPromotion(promotion_id=promotion_id, item_count=item_count)


async def query_promotion_jobs(
    db: AsyncSession,
    current_user: User,
    novel_id: uuid.UUID,
    limit: int,
    promotion_ids: list[uuid.UUID] | None = None,
) -> list[schemas.LabelPromotionJob]:
    job, item = models.LabelPromotionJob, models.LabelPromotionJobItem
    query = (
        select(
            job,
            func.count(item.auto_label_id).filter(item.outcome == PromotionItemOutcome.DONE),
            func.count(item.auto_label_id).filter(item.outcome == PromotionItemOutcome.FAILED),
            func.count(item.auto_label_id).filter(item.outcome.is_(None)),
        )
        .outerjoin(item, item.promotion_id == job.promotion_id)
        .join(LabelGroup, LabelGroup.label_group_id == job.label_group_id)
        .where(LabelGroup.novel_id == novel_id)
        .group_by(job.promotion_id)
        .order_by(job.status.in_(_ACTIVE).desc(), job.updated_at.desc())
        .limit(limit)
    )
    if promotion_ids is not None:
        query = query.where(job.promotion_id.in_(promotion_ids))
    query = label_group_mod_access_select(query, current_user)
    return [
        schemas.LabelPromotionJob(
            promotion_id=row.promotion_id,
            run_id=row.run_id,
            label_group_id=row.label_group_id,
            status=row.status,
            message=row.message,
            counts=schemas.LabelPromotionCounts(
                total=done + failed + pending, done=done, failed=failed, pending=pending
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row, done, failed, pending in await db.execute(query)
    ]


async def query_promotion_failures(
    db: AsyncSession, current_user: User, promotion_id: uuid.UUID, limit: int, offset: int
) -> list[schemas.LabelPromotionFailure]:
    item = models.LabelPromotionJobItem
    query = (
        select(nm.Chapter.chapter_id, nm.Chapter.chapter_num, item.message)
        .select_from(item)
        .join(models.LabelPromotionJob, models.LabelPromotionJob.promotion_id == item.promotion_id)
        .join(LabelGroup, LabelGroup.label_group_id == models.LabelPromotionJob.label_group_id)
        .join(models.AutoLabel, models.AutoLabel.auto_label_id == item.auto_label_id)
        .join(nm.ChapterContent, nm.ChapterContent.chapter_content_id == models.AutoLabel.chapter_content_id)
        .join(nm.Chapter, nm.Chapter.chapter_id == nm.ChapterContent.chapter_id)
        .where(item.promotion_id == promotion_id, item.outcome == PromotionItemOutcome.FAILED)
        .order_by(item.position)
        .limit(limit)
        .offset(offset)
    )
    query = label_group_mod_access_select(query, current_user)
    return [
        schemas.LabelPromotionFailure(chapter_id=chapter_id, chapter_num=chapter_num, message=message or "")
        for chapter_id, chapter_num, message in await db.execute(query)
    ]
