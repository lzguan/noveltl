import logging
import uuid

from src.autolabels.promotions.processing import PromotionClaimLostError, process_promotion_job
from src.autolabels.promotions.task_names import PROMOTE_LABELS
from src.database import AsyncSessionLocal
from src.jobs.broker import broker
from src.models import Base  # noqa: F401  registers every mapper for the worker process

logger = logging.getLogger(__name__)


@broker.task(task_name=PROMOTE_LABELS)
async def promote_labels(promotion_id: str) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await process_promotion_job(db, uuid.UUID(promotion_id))
        except PromotionClaimLostError:
            # Another worker reclaimed the job after this one's lease expired; it continues from here.
            logger.warning("Label promotion claim lost promotion_id=%s", promotion_id)
