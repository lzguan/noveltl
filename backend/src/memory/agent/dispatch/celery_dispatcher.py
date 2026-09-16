"""Publishing side of the memory-agent queue; no agent implementation imports.

Work is published by task name through `send_task`, so an API process never
imports the task functions or the provider SDK behind them. The worker registers
the matching names in `src.memory.agent.dispatch.celery`.
"""

import asyncio
import logging
from uuid import UUID

from src.memory.agent.celery_app import app
from src.memory.agent.dispatch.dispatcher import MemoryAgentDispatcher
from src.memory.agent.task_names import RUN_MEMORY_JOB, RUN_MEMORY_TASK
from src.memory.exceptions import MemoryAgentEnqueueFailedException

logger = logging.getLogger(__name__)


class CeleryMemoryAgentDispatcher(MemoryAgentDispatcher):
    """Publish memory-agent work to Celery using JSON-safe identifiers."""

    def enqueue_job(self, memory_job_id: UUID) -> None:
        try:
            logger.info("Enqueuing memory-agent job job_id=%s", memory_job_id)
            app.send_task(RUN_MEMORY_JOB, args=(str(memory_job_id),), task_id=str(memory_job_id))
        except Exception as exc:
            logger.exception("Memory-agent job enqueue failed job_id=%s", memory_job_id)
            raise MemoryAgentEnqueueFailedException(f"Celery enqueue failed: {exc}") from exc

    def enqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        try:
            logger.info("Enqueuing memory-agent task job_id=%s chapter_id=%s", memory_job_id, chapter_id)
            app.send_task(
                RUN_MEMORY_TASK,
                args=(str(memory_job_id), str(chapter_id)),
                task_id=f"{memory_job_id}:{chapter_id}",
            )
        except Exception as exc:
            logger.exception("Memory-agent task enqueue failed job_id=%s chapter_id=%s", memory_job_id, chapter_id)
            raise MemoryAgentEnqueueFailedException(f"Celery enqueue failed: {exc}") from exc

    async def aenqueue_job(self, memory_job_id: UUID) -> None:
        await asyncio.to_thread(self.enqueue_job, memory_job_id)

    async def aenqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        await asyncio.to_thread(self.enqueue_task, memory_job_id, chapter_id)
