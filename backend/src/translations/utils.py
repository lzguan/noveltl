import uuid
from typing import Protocol

from arq import ArqRedis
from redis.exceptions import ConnectionError, ResponseError, TimeoutError

from .exceptions import TranslationEnqueueFailedException, TranslationQueueFullException


class TranslationDispatcher(Protocol):
    """
    Abstract dispatcher for enqueuing a novel translation job to some queue.
    """

    async def enqueue(
        self,
        job_id: str,
        translation_job_id: uuid.UUID,
        source_novel_id: uuid.UUID,
        target_language_code: str,
        glossary_id: uuid.UUID | None,
        model_name: str | None,
    ) -> None:
        """
        Enqueue a novel translation request.

        Args:
            job_id: String id to queue job with (for ARQ deduplication).
            translation_job_id: UUID identifier for the NovelTranslationJob in the db.
            source_novel_id: UUID of the source novel to translate.
            target_language_code: ISO 639-1 code for the target language.
            glossary_id: Optional UUID of the glossary to use for term consistency.
            model_name: Name of the LLM model to use, or None for default.

        Raises:
            TranslationQueueFullException: Queue is full.
            TranslationEnqueueFailedException: Enqueue failed for some other reason.
        """
        ...


class ArqTranslationDispatcher:
    def __init__(self, redis_pool: ArqRedis) -> None:
        self.redis = redis_pool

    async def enqueue(
        self,
        job_id: str,
        translation_job_id: uuid.UUID,
        source_novel_id: uuid.UUID,
        target_language_code: str,
        glossary_id: uuid.UUID | None,
        model_name: str | None,
    ) -> None:
        try:
            await self.redis.enqueue_job(
                "translate_novel",
                job_id,
                translation_job_id,
                source_novel_id,
                target_language_code,
                glossary_id,
                model_name,
                _job_id=job_id,
            )
        except (ConnectionError, TimeoutError, OSError) as e:
            raise TranslationEnqueueFailedException(f"Redis connection failed: {str(e)}") from e
        except ResponseError as e:
            if "OOM" in str(e):
                raise TranslationQueueFullException("Redis memory is full") from e
            raise TranslationEnqueueFailedException(f"Redis protocol error: {str(e)}") from e
        except (TypeError, ValueError) as e:
            raise TranslationEnqueueFailedException(f"Failed to serialize job data: {str(e)}") from e
