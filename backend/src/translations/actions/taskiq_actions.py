import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from taskiq import AsyncBroker, AsyncTaskiqDecoratedTask, ScheduleSource

from src.config import database_settings
from src.translations.actions.actions import (
    ActionCallback,
    ActionCallbacks,
    ActionStep,
    ActionTask,
    ActionTaskContext,
    PollCallback,
)
from src.translations.actions.runner import ready_next_task, run_claimed_step
from src.translations.types import ActionName, TranslationTaskStatus

# One event loop serves every step in a worker process, so its connections are pooled.
_taskiq_engine = create_async_engine(database_settings.DB_URL, pool_size=20)
TaskiqSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _taskiq_engine, autoflush=False, expire_on_commit=False
)

type _StepTask = AsyncTaskiqDecoratedTask[..., Coroutine[Any, Any, None]]


class TaskiqActionCallbacks(ActionCallbacks):
    def __init__(
        self,
        broker: AsyncBroker,
        schedule_source: ScheduleSource,
        callbacks_dict: dict[ActionName, ActionCallbacks],
    ) -> None:
        self.broker = broker
        self.schedule_source = schedule_source
        self._intermediate: list[_StepTask] = []
        self._steps: list[ActionStep] = []
        self._callbacks_dict = callbacks_dict

    def new_func(
        self,
        *,
        expect: TranslationTaskStatus,
        during: TranslationTaskStatus,
        finish: TranslationTaskStatus,
        lease_seconds: int = 300,
        name: str | None = None,
    ) -> Callable[[ActionCallback], ActionTask]:
        def decorate(f: ActionCallback) -> ActionTask:
            async def run(context: ActionTaskContext) -> bool:
                await f(context)
                return True

            return self._register(
                run,
                name=name if name is not None else f"{f.__module__}.{f.__qualname__}",
                expect=expect,
                during=during,
                finish=finish,
                lease_seconds=lease_seconds,
            )

        return decorate

    def new_poll(
        self,
        *,
        expect: TranslationTaskStatus,
        during: TranslationTaskStatus,
        finish: TranslationTaskStatus,
        interval_seconds: int = 60,
        lease_seconds: int = 300,
        name: str | None = None,
    ) -> Callable[[PollCallback], ActionTask]:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        def decorate(f: PollCallback) -> ActionTask:
            return self._register(
                f,
                name=name if name is not None else f"{f.__module__}.{f.__qualname__}",
                expect=expect,
                during=during,
                finish=finish,
                lease_seconds=lease_seconds,
                interval_seconds=interval_seconds,
            )

        return decorate

    def _register(
        self,
        f: PollCallback,
        *,
        name: str,
        expect: TranslationTaskStatus,
        during: TranslationTaskStatus,
        finish: TranslationTaskStatus,
        lease_seconds: int,
        interval_seconds: int = 60,
    ) -> ActionTask:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        duration = timedelta(seconds=lease_seconds)
        idx = len(self._intermediate)

        async def run_step(x: uuid.UUID) -> None:
            outcome = await run_claimed_step(
                TaskiqSessionLocal,
                x,
                f,
                expect=expect,
                during=during,
                finish=finish,
                duration=duration,
                interval_seconds=interval_seconds,
            )
            if outcome == "unclaimed":
                return
            if outcome == "pending":
                await dispatch(x, delay=timedelta(seconds=interval_seconds))
            elif idx + 1 < len(self._intermediate):
                await self._intermediate[idx + 1].kiq(str(x))
            else:
                await self.exitpoint(x)

        # Messages carry the task ID as a string; the payload must be JSON.
        @self.broker.task(task_name=name)
        async def taskiq_task(task_id: str) -> None:
            await run_step(uuid.UUID(task_id))

        self._intermediate.append(taskiq_task)

        async def dispatch(task_id: uuid.UUID, *, delay: timedelta | None = None) -> None:
            # A deadline already passed means the gate is open; send at once.
            if delay is None or delay <= timedelta(0):
                await taskiq_task.kiq(str(task_id))
            else:
                # Never earlier than the deadline: the poll gate drops an early message.
                await taskiq_task.schedule_by_time(self.schedule_source, datetime.now(UTC) + delay, str(task_id))

        self._steps.append(ActionStep(expect, during, finish, dispatch))
        return run_step

    def resume_step(self, state: TranslationTaskStatus) -> ActionStep | None:
        if state == TranslationTaskStatus.COMPLETE:
            return None
        if state == TranslationTaskStatus.WAITING and self._steps:
            return self._steps[0]
        # Prefer the next step at a boundary, e.g. PROCESSING selects polling.
        for step in self._steps:
            if step.expect == state:
                return step
        for step in self._steps:
            if step.during == state:
                return step
        raise ValueError(f"No registered action step for state {state}")

    async def entrypoint(self, x: uuid.UUID) -> None:
        if self._intermediate:
            await self._intermediate[0].kiq(str(x))
        else:
            await self.exitpoint(x)

    async def exitpoint(self, x: uuid.UUID) -> None:
        ready = await ready_next_task(TaskiqSessionLocal, x)
        if ready is None:
            return
        next_task_id, next_action = ready
        # A failed dispatch leaves the task READY so exitpoint can be retried.
        next_callbacks = self._callbacks_dict[TypeAdapter(ActionName).validate_python(next_action)]
        await next_callbacks.entrypoint(next_task_id)
