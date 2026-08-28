import asyncio
import logging
from uuid import UUID

from src.database import SessionLocal
from src.memory.agent.celery_app import app
from src.memory.agent.dispatch.dispatcher import MemoryAgentDispatcher
from src.memory.agent.tasks.tasks import run_all_tasks, run_task
from src.memory.exceptions import MemoryAgentEnqueueFailedException

logger = logging.getLogger(__name__)


@app.task
def run_memory_job(memory_job_id: str) -> None:
    """Celery entry point for processing every pending task in a memory job."""

    async def consume_job() -> None:
        # Agent results are transient; durable progress is recorded by each task.
        async for _ in run_all_tasks(SessionLocal, UUID(memory_job_id)):
            pass

    asyncio.run(consume_job())


@app.task
def run_memory_task(memory_job_id: str, chapter_id: str) -> None:
    """Celery entry point for processing one pending chapter task."""
    asyncio.run(run_task(SessionLocal, UUID(memory_job_id), UUID(chapter_id)))


class CeleryMemoryAgentDispatcher(MemoryAgentDispatcher):
    """Publish memory-agent work to Celery using JSON-safe identifiers."""

    def enqueue_job(self, memory_job_id: UUID) -> None:
        try:
            logger.info("Enqueuing memory-agent job job_id=%s", memory_job_id)
            run_memory_job.apply_async((str(memory_job_id),), task_id=str(memory_job_id))
        except Exception as exc:
            logger.exception("Memory-agent job enqueue failed job_id=%s", memory_job_id)
            raise MemoryAgentEnqueueFailedException(f"Celery enqueue failed: {exc}") from exc

    def enqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        try:
            logger.info("Enqueuing memory-agent task job_id=%s chapter_id=%s", memory_job_id, chapter_id)
            run_memory_task.apply_async(
                (str(memory_job_id), str(chapter_id)),
                task_id=f"{memory_job_id}:{chapter_id}",
            )
        except Exception as exc:
            logger.exception("Memory-agent task enqueue failed job_id=%s chapter_id=%s", memory_job_id, chapter_id)
            raise MemoryAgentEnqueueFailedException(f"Celery enqueue failed: {exc}") from exc

    async def aenqueue_job(self, memory_job_id: UUID) -> None:
        await asyncio.to_thread(self.enqueue_job, memory_job_id)

    async def aenqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        await asyncio.to_thread(self.enqueue_task, memory_job_id, chapter_id)
