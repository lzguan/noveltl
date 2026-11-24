import logging
import uuid

from src.autolabels.promotions.dispatch.taskiq_dispatcher import TaskiqPromotionDispatcher
from src.autolabels.promotions.processing import PromotionClaimLostError, process_promotion_job
from src.autolabels.promotions.sweeper import sweep_stale_promotions
from src.autolabels.promotions.task_names import PROMOTE_LABELS, SWEEP_STALE_PROMOTIONS
from src.database import AsyncSessionLocal
from src.jobs.broker import broker
from src.models import Base  # noqa: F401  registers every mapper for the worker process

logger = logging.getLogger(__name__)

SWEEP_STALE_PROMOTIONS_CRON = "* * * * *"


@broker.task(task_name=PROMOTE_LABELS)
async def promote_labels(promotion_id: str) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await process_promotion_job(db, uuid.UUID(promotion_id))
        except PromotionClaimLostError:
            # Another worker reclaimed the job after this one's lease expired; it continues from here.
            logger.warning("Label promotion claim lost promotion_id=%s", promotion_id)


@broker.task(
    task_name=SWEEP_STALE_PROMOTIONS,
    schedule=[{"cron": SWEEP_STALE_PROMOTIONS_CRON}],
)
async def sweep_stale_promotions_task() -> None:
    dispatcher = TaskiqPromotionDispatcher()
    async with AsyncSessionLocal() as db:
        await sweep_stale_promotions(db, dispatcher)
