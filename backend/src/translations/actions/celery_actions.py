import uuid
from collections.abc import Callable
from datetime import timedelta

from celery import Celery
from celery.app.task import Task
from pydantic import TypeAdapter

from src.autolabels.worker.config import SessionLocal
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


class CeleryActionCallbacks(ActionCallbacks):
    def __init__(self, celery_app: Celery, callbacks_dict: dict[ActionName, ActionCallbacks]) -> None:
        self.celery_app = celery_app
        self._intermediate: list[Task] = []
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
            def run(context: ActionTaskContext) -> bool:
                f(context)
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

        @self.celery_app.task(name=name, shared=False)
        def celery_task(x: uuid.UUID) -> None:
            outcome = run_claimed_step(
                SessionLocal,
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
                dispatch(x, delay=timedelta(seconds=interval_seconds))
            elif idx + 1 < len(self._intermediate):
                self._intermediate[idx + 1].apply_async((x,))
            else:
                self.exitpoint(x)

        self._intermediate.append(celery_task)

        def dispatch(task_id: uuid.UUID, *, delay: timedelta | None = None) -> None:
            if delay is None:
                celery_task.apply_async((task_id,))
            else:
                # A deadline already passed means the gate is open; fire at once.
                celery_task.apply_async((task_id,), countdown=max(delay, timedelta(0)).total_seconds())

        self._steps.append(ActionStep(expect, during, finish, dispatch))
        return celery_task

    def last_step(self, state: TranslationTaskStatus) -> ActionStep | None:
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

    def entrypoint(self, x: uuid.UUID) -> None:
        if self._intermediate:
            self._intermediate[0].apply_async((x,))
        else:
            self.exitpoint(x)

    def exitpoint(self, x: uuid.UUID) -> None:
        ready = ready_next_task(SessionLocal, x)
        if ready is None:
            return
        next_task_id, next_action = ready
        # A failed dispatch leaves the task READY so exitpoint can be retried.
        next_callbacks = self._callbacks_dict[TypeAdapter(ActionName).validate_python(next_action)]
        next_callbacks.entrypoint(next_task_id)
