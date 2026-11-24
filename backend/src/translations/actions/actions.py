"""Callback contracts; action implementations and worker wiring live elsewhere."""

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.translations.models import TranslationTask
from src.translations.types import TranslationTaskStatus


@dataclass(frozen=True)
class ActionTaskContext:
    db: AsyncSession
    task: TranslationTask


type ActionCallback = Callable[[ActionTaskContext], Awaitable[None]]
type PollCallback = Callable[[ActionTaskContext], Awaitable[bool]]
type ActionTask = Callable[[uuid.UUID], Awaitable[None]]


class StepDispatcher(Protocol):
    def __call__(self, task_id: uuid.UUID, *, delay: timedelta | None = None) -> Awaitable[None]: ...


@dataclass(frozen=True)
class ActionStep:
    expect: TranslationTaskStatus
    during: TranslationTaskStatus
    finish: TranslationTaskStatus
    dispatch: StepDispatcher


class ActionCallbacks(Protocol):
    """
    Conceptually, entrypoint should be a function that dispatches a task to the "next" step in this action, and exitpoint should be a function that dispatches the entrypoint to the "next" action in the stages pipeline. new_func should take a plain function and record it as a dispatcher for a step in this action, which then automatically dispatches the next step at the end.

    In practice the implementation will be absolutely cursed. This doesn't matter because this is a personal project, but I would not recommend using this as a model for your own code. Admittedly this implementation is kind of an experiment.
    """

    async def entrypoint(self, x: uuid.UUID) -> None: ...

    def resume_step(self, state: TranslationTaskStatus) -> ActionStep | None: ...

    def new_func(
        self,
        *,
        expect: TranslationTaskStatus,
        during: TranslationTaskStatus,
        finish: TranslationTaskStatus,
        lease_seconds: int = 300,
        name: str | None = None,
    ) -> Callable[[ActionCallback], ActionTask]: ...

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
        """False releases and reschedules this step; True advances; errors fail."""
        ...


@dataclass(frozen=True)
class StepSpec:
    callback: ActionCallback
    name: str
    expect: TranslationTaskStatus
    during: TranslationTaskStatus
    finish: TranslationTaskStatus
    lease_seconds: int = 300


@dataclass(frozen=True)
class PollSpec:
    callback: PollCallback
    name: str
    expect: TranslationTaskStatus
    during: TranslationTaskStatus
    finish: TranslationTaskStatus
    interval_seconds: int = 60
    lease_seconds: int = 300


type ActionStepSpec = StepSpec | PollSpec


def register_steps(callbacks: ActionCallbacks, steps: Sequence[ActionStepSpec]) -> tuple[ActionTask, ...]:
    registered: list[ActionTask] = []
    for step in steps:
        match step:
            case StepSpec():
                registered.append(
                    callbacks.new_func(
                        expect=step.expect,
                        during=step.during,
                        finish=step.finish,
                        lease_seconds=step.lease_seconds,
                        name=step.name,
                    )(step.callback)
                )
            case PollSpec():
                registered.append(
                    callbacks.new_poll(
                        expect=step.expect,
                        during=step.during,
                        finish=step.finish,
                        interval_seconds=step.interval_seconds,
                        lease_seconds=step.lease_seconds,
                        name=step.name,
                    )(step.callback)
                )
    return tuple(registered)
