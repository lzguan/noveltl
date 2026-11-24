import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from src.translations.celery_app import app


def celery_step(name: str) -> Callable[[UUID], Awaitable[None]]:
    # The task body calls asyncio.run, which cannot nest in a test's loop; run it in a thread.
    task = app.tasks[name]

    async def run(task_id: UUID) -> None:
        await asyncio.to_thread(task, task_id)

    return run
