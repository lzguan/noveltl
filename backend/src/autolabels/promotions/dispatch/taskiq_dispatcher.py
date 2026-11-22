import logging
import uuid
from collections.abc import Coroutine
from typing import Any

from taskiq.kicker import AsyncKicker

from src.autolabels.exceptions import EnqueueFailedException
from src.autolabels.promotions.dispatch.dispatcher import PromotionDispatcher
from src.autolabels.promotions.task_names import PROMOTE_LABELS
from src.jobs.broker import broker

logger = logging.getLogger(__name__)

# Kicks the task by name, so an API process never imports the worker's task module.
# Typed with the task's signature, `promote_labels(promotion_id: str) -> None`.
_promote_labels: AsyncKicker[[str], Coroutine[Any, Any, None]] = AsyncKicker(
    task_name=PROMOTE_LABELS, broker=broker, labels={}
)


class TaskiqPromotionDispatcher(PromotionDispatcher):
    async def aenqueue(self, promotion_id: uuid.UUID) -> None:
        try:
            await _promote_labels.kiq(str(promotion_id))
        except Exception as e:
            logger.exception("Label promotion enqueue failed promotion_id=%s", promotion_id)
            raise EnqueueFailedException(f"Promotion enqueue failed: {e}") from e
