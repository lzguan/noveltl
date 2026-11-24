from collections.abc import Awaitable, Callable, Coroutine
from typing import Any
from uuid import UUID

from taskiq import AsyncTaskiqDecoratedTask

import src.translations.actions  # noqa: F401  registers every step task
from src.translations.broker import broker


def step_task(name: str) -> AsyncTaskiqDecoratedTask[..., Coroutine[Any, Any, None]]:
    task = broker.find_task(name)
    if task is None:
        raise KeyError(name)
    return task


def run_step(name: str) -> Callable[[UUID], Awaitable[None]]:
    # Calling a decorated task runs its body in place, as a worker would on delivery.
    task = step_task(name)

    async def run(task_id: UUID) -> None:
        await task(str(task_id))

    return run
