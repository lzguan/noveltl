import logging
import uuid
from typing import Protocol

from arq import ArqRedis
from redis.exceptions import ConnectionError, ResponseError, TimeoutError

from .exceptions import EnqueueFailedException, QueueFullException

logger = logging.getLogger(__name__)


class AutoLabelDispatcher(Protocol):
    """
    Abstract class for enqueuing an autolabel request to some queue.
    """

    async def enqueue(
        self,
        job_id: str,
        auto_label_id: uuid.UUID,
    ) -> None:
        """
        Enqueue a request.

        Args:
            job_id: String id to queue job with.
            auto_label_id: Integer identifier for the AutoLabel being operated on in db.
            params: Parameters for the NER model.

        Raises:
            QueueFullException: Queue is full.
            EnqueueFailedException: Enqueue failed for some other reason.
        """
        ...


class ArqDispatcher(AutoLabelDispatcher):
    def __init__(self, redis_pool: ArqRedis) -> None:
        self.redis = redis_pool

    async def enqueue(
        self,
        job_id: str,
        auto_label_id: uuid.UUID,
    ) -> None:
        try:
            logger.info("Enqueuing autolabel job job_id=%s auto_label_id=%s", job_id, auto_label_id)
            await self.redis.enqueue_job("autolabel_infer", job_id, auto_label_id, _job_id=job_id)
            logger.info("Autolabel job enqueued job_id=%s auto_label_id=%s", job_id, auto_label_id)
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.exception("Autolabel enqueue connection failure job_id=%s auto_label_id=%s", job_id, auto_label_id)
            raise EnqueueFailedException(f"Redis connection failed: {str(e)}") from e
        except ResponseError as e:
            if "OOM" in str(e):
                logger.exception("Autolabel enqueue queue full job_id=%s auto_label_id=%s", job_id, auto_label_id)
                raise QueueFullException("Redis memory is full") from e
            # If it's another protocol error, treat as generic failure
            logger.exception("Autolabel enqueue protocol failure job_id=%s auto_label_id=%s", job_id, auto_label_id)
            raise EnqueueFailedException(f"Redis protocol error: {str(e)}") from e
        except (TypeError, ValueError) as e:
            logger.exception("Autolabel enqueue serialization failure job_id=%s auto_label_id=%s", job_id, auto_label_id)
            raise EnqueueFailedException(f"Failed to serialize job data: {str(e)}") from e
