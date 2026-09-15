"""Callback contracts; action implementations and worker wiring live elsewhere."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from src.translations.models import TranslationTask
from src.translations.types import TranslationTaskStatus


@dataclass(frozen=True)
class ActionTaskContext:
    """Task and session owned by the current worker invocation.

    Callbacks may mutate the task and use the session, but must not commit,
    roll back, or close it. The wrapper owns the transaction and session lifetime.
    This context stays in the worker; queue messages contain only the task ID.
    Status, failure, and claim fields belong to the wrapper. Renew cooperatively
    before expiry during long work, before flushing or locking the task row:
    renewal uses its own transaction. A single blocking operation must fit
    within the lease. Renewal failure raises and prevents completion.
    """

    db: Session
    task: TranslationTask
    claim_token: uuid.UUID
    renew_lease: Callable[[], None]


type ActionCallback = Callable[[ActionTaskContext], None]
type PollCallback = Callable[[ActionTaskContext], bool]
type ActionTask = Callable[[uuid.UUID], None]


@dataclass(frozen=True)
class ActionStep:
    expect: TranslationTaskStatus
    during: TranslationTaskStatus
    finish: TranslationTaskStatus
    dispatch: ActionTask


class ActionCallbacks(Protocol):
    """
    Conceptually, entrypoint should be a function that dispatches a task to the "next" step in this action, and exitpoint should be a function that dispatches the entrypoint to the "next" action in the stages pipeline. new_func should take a plain function and record it as a dispatcher for a step in this action, which then automatically dispatches the next step at the end.

    In practice the implementation will be absolutely cursed. This doesn't matter because this is a personal project, but I would not recommend using this as a model for your own code. Admittedly this implementation is kind of an experiment.
    """

    def entrypoint(self, x: uuid.UUID) -> None: ...

    def exitpoint(self, x: uuid.UUID) -> None: ...

    def last_step(self, state: TranslationTaskStatus) -> ActionStep | None: ...

    def new_func(
        self,
        *,
        expect: TranslationTaskStatus,
        during: TranslationTaskStatus,
        finish: TranslationTaskStatus,
        lease_seconds: int = 300,
    ) -> Callable[[ActionCallback], ActionTask]: ...

    def new_poll(
        self,
        *,
        expect: TranslationTaskStatus,
        during: TranslationTaskStatus,
        finish: TranslationTaskStatus,
        interval_seconds: int = 60,
        lease_seconds: int = 300,
    ) -> Callable[[PollCallback], ActionTask]:
        """False releases and reschedules this step; True advances; errors fail."""
        ...
