import uuid
from typing import Protocol

from arq import ArqRedis
from redis.exceptions import ConnectionError, ResponseError, TimeoutError

from .exceptions import EnqueueFailedException, QueueFullException


class TranslationDispatcher(Protocol):
    """
    Abstract class for enqueuing a glossary translation request to some queue.
    """

    async def enqueue(
        self,
        job_id: str,
        translation_job_id: uuid.UUID,
        model_name: str | None,
    ) -> None:
        """
        Enqueue a translation request.

        Args:
            job_id: String id to queue job with.
            translation_job_id: UUID identifier for the GlossaryTranslationJob in the db.
            model_name: Name of the LLM model to use, or None for default.

        Raises:
            QueueFullException: Queue is full.
            EnqueueFailedException: Enqueue failed for some other reason.
        """
        ...


class ArqTranslationDispatcher(TranslationDispatcher):
    def __init__(self, redis_pool: ArqRedis) -> None:
        self.redis = redis_pool

    async def enqueue(
        self,
        job_id: str,
        translation_job_id: uuid.UUID,
        model_name: str | None,
    ) -> None:
        try:
            await self.redis.enqueue_job("glossary_translate", job_id, translation_job_id, model_name, _job_id=job_id)
        except (ConnectionError, TimeoutError, OSError) as e:
            raise EnqueueFailedException(f"Redis connection failed: {str(e)}") from e
        except ResponseError as e:
            if "OOM" in str(e):
                raise QueueFullException("Redis memory is full") from e
            raise EnqueueFailedException(f"Redis protocol error: {str(e)}") from e
        except (TypeError, ValueError) as e:
            raise EnqueueFailedException(f"Failed to serialize job data: {str(e)}") from e
