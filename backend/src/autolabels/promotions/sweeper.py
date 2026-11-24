import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.autolabels.constants import AutoLabelProgress
from src.autolabels.models import LabelPromotionJob
from src.autolabels.promotions.dispatch.dispatcher import PromotionDispatcher

logger = logging.getLogger(__name__)

PENDING_PROMOTION_GRACE_PERIOD = timedelta(seconds=30)


@dataclass(frozen=True)
class PromotionSweepResult:
    enqueued: tuple[uuid.UUID, ...]
    failed: tuple[uuid.UUID, ...]


async def find_stale_promotion_ids(
    db: AsyncSession,
    *,
    pending_grace: timedelta = PENDING_PROMOTION_GRACE_PERIOD,
    limit: int | None = None,
) -> list[uuid.UUID]:
    now = func.clock_timestamp()
    query = (
        select(LabelPromotionJob.promotion_id)
        .where(
            or_(
                and_(
                    LabelPromotionJob.status == AutoLabelProgress.PENDING,
                    LabelPromotionJob.updated_at <= now - pending_grace,
                ),
                and_(
                    LabelPromotionJob.status == AutoLabelProgress.PROCESSING,
                    LabelPromotionJob.claim_expires_at <= now,
                ),
            )
        )
        .order_by(LabelPromotionJob.updated_at.asc(), LabelPromotionJob.promotion_id.asc())
    )
    if limit is not None:
        query = query.limit(limit)
    promotion_ids = list((await db.execute(query)).scalars())
    # Release the read transaction before callers perform broker I/O.
    await db.commit()
    return promotion_ids


async def sweep_stale_promotions(
    db: AsyncSession,
    dispatcher: PromotionDispatcher,
    *,
    pending_grace: timedelta = PENDING_PROMOTION_GRACE_PERIOD,
    limit: int | None = None,
) -> PromotionSweepResult:
    promotion_ids = await find_stale_promotion_ids(db, pending_grace=pending_grace, limit=limit)
    enqueued: list[uuid.UUID] = []
    failed: list[uuid.UUID] = []
    for promotion_id in promotion_ids:
        try:
            await dispatcher.aenqueue(promotion_id)
        except Exception:
            logger.exception("Failed to redispatch stale promotion promotion_id=%s", promotion_id)
            failed.append(promotion_id)
        else:
            enqueued.append(promotion_id)
    if enqueued or failed:
        logger.info("Promotion sweep finished enqueued=%s failed=%s", len(enqueued), len(failed))
    return PromotionSweepResult(enqueued=tuple(enqueued), failed=tuple(failed))
