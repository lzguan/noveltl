"""Worker-side task registration; imports the agent implementation and its SDK."""

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import database_settings
from src.memory.agent.broker import broker
from src.memory.agent.dispatch.log_results import log_agent_result
from src.memory.agent.task_names import RUN_MEMORY_JOB, RUN_MEMORY_TASK
from src.memory.agent.tasks.tasks import run_all_tasks, run_one_task
from src.models import Base  # noqa: F401  registers every mapper for the worker process

# Tools commit before each model request, so a task holds a connection only while its
# queries run; a task waiting for a free connection yields the event loop.
worker_engine = create_async_engine(database_settings.DB_URL, pool_size=20)
WorkerSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    worker_engine, autoflush=False, expire_on_commit=False
)


@broker.task(task_name=RUN_MEMORY_JOB)
async def run_memory_job(memory_job_id: str) -> None:
    """Taskiq entry point for processing every pending task in a memory job."""
    async for completed_task in run_all_tasks(WorkerSessionLocal, UUID(memory_job_id)):
        # Serializing a full message history can take a while; keep it off the event loop.
        await asyncio.to_thread(log_agent_result, completed_task)


@broker.task(task_name=RUN_MEMORY_TASK)
async def run_memory_task(memory_job_id: str, chapter_id: str, stage_num: int = 0) -> None:
    """Taskiq entry point for processing one pending chapter task."""
    completed_task = await run_one_task(WorkerSessionLocal, UUID(memory_job_id), UUID(chapter_id), stage_num)
    if completed_task is not None:
        await asyncio.to_thread(log_agent_result, completed_task)
