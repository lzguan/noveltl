"""Worker-side task registration; imports the agent implementation and its SDK."""

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import database_settings
from src.memory.agent.celery_app import app
from src.memory.agent.dispatch.log_results import log_agent_result
from src.memory.agent.task_names import RUN_MEMORY_JOB, RUN_MEMORY_TASK
from src.memory.agent.tasks.tasks import run_all_tasks, run_one_task

# Each task runs its own asyncio.run event loop, and pooled async connections cannot
# move between loops, so every session opens a fresh connection.
celery_engine = create_async_engine(database_settings.DB_URL, poolclass=NullPool)
CelerySessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    celery_engine, autoflush=False, expire_on_commit=False
)


@app.task(name=RUN_MEMORY_JOB)
def run_memory_job(memory_job_id: str) -> None:
    """Celery entry point for processing every pending task in a memory job."""

    async def consume_job() -> None:
        async for completed_task in run_all_tasks(CelerySessionLocal, UUID(memory_job_id)):
            log_agent_result(completed_task)

    asyncio.run(consume_job())


@app.task(name=RUN_MEMORY_TASK)
def run_memory_task(memory_job_id: str, chapter_id: str, stage_num: int = 0) -> None:
    """Celery entry point for processing one pending chapter task."""
    completed_task = asyncio.run(run_one_task(CelerySessionLocal, UUID(memory_job_id), UUID(chapter_id), stage_num))
    if completed_task is not None:
        log_agent_result(completed_task)
