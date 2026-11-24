"""Not audited, strictly for agent eval use."""

import asyncio
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.translations.actions import load_inputs, prune_memories, translate
from src.translations.actions.actions import (
    ActionCallback,
    ActionCallbacks,
    ActionStep,
    ActionStepSpec,
    ActionTask,
    ActionTaskContext,
    PollCallback,
    register_steps,
)
from src.translations.actions.runner import StepOutcome, ready_next_task, run_claimed_step
from src.translations.types import ActionName, TranslationTaskStatus


@dataclass(frozen=True)
class _Step:
    callback: PollCallback
    expect: TranslationTaskStatus
    during: TranslationTaskStatus
    finish: TranslationTaskStatus
    duration: timedelta
    interval_seconds: int


class AsyncActionCallbacks(ActionCallbacks):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        callbacks_dict: Mapping[ActionName, ActionCallbacks],
        semaphore: asyncio.Semaphore,
    ) -> None:
        self._session_factory = session_factory
        self._callbacks_dict = callbacks_dict
        self._semaphore = semaphore
        self._registered: list[_Step] = []
        self._steps: list[ActionStep] = []

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

            return self._register(run, expect, during, finish, lease_seconds, interval_seconds=60)

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
            return self._register(f, expect, during, finish, lease_seconds, interval_seconds=interval_seconds)

        return decorate

    def _register(
        self,
        f: PollCallback,
        expect: TranslationTaskStatus,
        during: TranslationTaskStatus,
        finish: TranslationTaskStatus,
        lease_seconds: int,
        *,
        interval_seconds: int,
    ) -> ActionTask:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        step = _Step(f, expect, during, finish, timedelta(seconds=lease_seconds), interval_seconds)
        index = len(self._registered)
        self._registered.append(step)

        async def dispatch(task_id: uuid.UUID, *, delay: timedelta | None = None) -> None:
            if delay is not None:
                await asyncio.sleep(max(delay, timedelta(0)).total_seconds())
            await self._run_from(index, task_id)

        self._steps.append(ActionStep(expect, during, finish, dispatch))

        async def run_once(task_id: uuid.UUID) -> None:
            await self._claim_and_run(step, task_id)

        return run_once

    async def _claim_and_run(self, step: _Step, task_id: uuid.UUID) -> StepOutcome:
        return await run_claimed_step(
            self._session_factory,
            task_id,
            step.callback,
            expect=step.expect,
            during=step.during,
            finish=step.finish,
            duration=step.duration,
            interval_seconds=step.interval_seconds,
        )

    async def _run_from(self, index: int, task_id: uuid.UUID) -> None:
        while index < len(self._registered):
            step = self._registered[index]
            async with self._semaphore:
                outcome = await self._claim_and_run(step, task_id)
            if outcome == "unclaimed":
                return
            if outcome == "pending":
                await asyncio.sleep(step.interval_seconds)
                continue
            index += 1
        await self.exitpoint(task_id)

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
        await self._run_from(0, x)

    async def exitpoint(self, x: uuid.UUID) -> None:
        ready = await ready_next_task(self._session_factory, x)
        if ready is None:
            return
        next_task_id, next_action = ready
        await self._callbacks_dict[TypeAdapter(ActionName).validate_python(next_action)].entrypoint(next_task_id)


_ACTION_STEPS: tuple[tuple[ActionName, tuple[ActionStepSpec, ...]], ...] = (
    ("load_inputs", load_inputs.STEPS),
    ("prune_memories", prune_memories.STEPS),
    ("translate", translate.STEPS),
)


def build_async_registry(
    session_factory: async_sessionmaker[AsyncSession], *, max_concurrent_steps: int = 4
) -> dict[ActionName, ActionCallbacks]:
    if max_concurrent_steps <= 0:
        raise ValueError("max_concurrent_steps must be positive")
    registry: dict[ActionName, ActionCallbacks] = {}
    semaphore = asyncio.Semaphore(max_concurrent_steps)
    for name, steps in _ACTION_STEPS:
        callbacks = AsyncActionCallbacks(session_factory, registry, semaphore)
        register_steps(callbacks, steps)
        registry[name] = callbacks
    return registry
