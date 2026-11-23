"""Worker-side task registration; imports the agent implementation and its SDK."""

import asyncio
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import database_settings
from src.memory.agent.broker import broker
from src.memory.agent.dispatch.log_results import log_agent_result
from src.memory.agent.task_names import RUN_MEMORY_JOB, RUN_MEMORY_TASK
from src.memory.agent.tasks.tasks import run_all_tasks, run_one_task
from src.models import Base  # noqa: F401  registers every mapper for the worker process

# Tools commit before each model request, so a task holds a connection only while a tool
# or its own bookkeeping runs. pydantic-ai runs sync tools in anyio's worker threads (40
# by default), so the pool matches that many concurrent tool calls.
worker_engine = create_engine(database_settings.DB_URL, pool_size=40, max_overflow=0, pool_timeout=10)
WorkerSessionLocal: sessionmaker[Session] = sessionmaker(autoflush=False, bind=worker_engine)


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
