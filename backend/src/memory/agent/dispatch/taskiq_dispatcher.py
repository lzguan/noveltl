"""Publishing side of the memory-agent queue; no agent implementation imports.

Work is kicked by task name, so an API process never imports the task functions or
the provider SDK behind them. The worker registers the matching names in
`src.memory.agent.dispatch.taskiq_worker`.
"""

import logging
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from taskiq.kicker import AsyncKicker

from src.memory.agent.broker import broker
from src.memory.agent.dispatch.dispatcher import MemoryAgentDispatcher
from src.memory.agent.task_names import RUN_MEMORY_JOB, RUN_MEMORY_TASK
from src.memory.exceptions import MemoryAgentEnqueueFailedException

logger = logging.getLogger(__name__)

# Typed with the tasks' signatures in `src.memory.agent.dispatch.taskiq_worker`.
_run_memory_job: AsyncKicker[[str], Coroutine[Any, Any, None]] = AsyncKicker(
    task_name=RUN_MEMORY_JOB, broker=broker, labels={}
)
_run_memory_task: AsyncKicker[[str, str, int], Coroutine[Any, Any, None]] = AsyncKicker(
    task_name=RUN_MEMORY_TASK, broker=broker, labels={}
)


class TaskiqMemoryAgentDispatcher(MemoryAgentDispatcher):
    """Publish memory-agent work to taskiq using JSON-safe identifiers."""

    async def aenqueue_job(self, memory_job_id: UUID) -> None:
        try:
            logger.info("Enqueuing memory-agent job job_id=%s", memory_job_id)
            await _run_memory_job.kiq(str(memory_job_id))
        except Exception as exc:
            logger.exception("Memory-agent job enqueue failed job_id=%s", memory_job_id)
            raise MemoryAgentEnqueueFailedException(f"Memory-agent enqueue failed: {exc}") from exc

    async def aenqueue_task(self, memory_job_id: UUID, chapter_id: UUID, stage_num: int = 0) -> None:
        try:
            logger.info("Enqueuing memory-agent task job_id=%s chapter_id=%s", memory_job_id, chapter_id)
            await _run_memory_task.kiq(str(memory_job_id), str(chapter_id), stage_num)
        except Exception as exc:
            logger.exception("Memory-agent task enqueue failed job_id=%s chapter_id=%s", memory_job_id, chapter_id)
            raise MemoryAgentEnqueueFailedException(f"Memory-agent enqueue failed: {exc}") from exc
