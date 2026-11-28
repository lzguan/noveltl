import logging
import uuid
from collections.abc import Coroutine
from typing import Any, Protocol

from taskiq.kicker import AsyncKicker

from src.jobs.broker import broker
from src.publishing.exceptions import PublishEnqueueFailedException

logger = logging.getLogger(__name__)

PUBLISH_NOVEL = "publishing.publish_novel"


class PublishDispatcher(Protocol):
    async def aenqueue(self, job_id: uuid.UUID) -> None: ...


_publish_novel: AsyncKicker[[str], Coroutine[Any, Any, None]] = AsyncKicker(
    task_name=PUBLISH_NOVEL, broker=broker, labels={}
)


class TaskiqPublishDispatcher(PublishDispatcher):
    async def aenqueue(self, job_id: uuid.UUID) -> None:
        try:
            await _publish_novel.kiq(str(job_id))
        except Exception as e:
            logger.exception("Publish job enqueue failed job_id=%s", job_id)
            raise PublishEnqueueFailedException(f"Publish job enqueue failed: {e}") from e
