import uuid
from collections.abc import Callable
from datetime import timedelta

from celery import Celery
from celery.app.task import Task
from pydantic import TypeAdapter
from sqlalchemy import select, update
from sqlalchemy.orm import aliased

from src.autolabels.worker.config import SessionLocal
from src.translations.actions.actions import (
    ActionCallback,
    ActionCallbacks,
    ActionStep,
    ActionTask,
    ActionTaskContext,
    PollCallback,
)
from src.translations.models import TranslationStage, TranslationTask
from src.translations.tasks.claims import TranslationClaimLostError, claim_task, fail_claim, finish_claim, renew_claim
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
    ) -> Callable[[ActionCallback], ActionTask]:
        def decorate(f: ActionCallback) -> ActionTask:
            def run(context: ActionTaskContext) -> bool:
                f(context)
                return True

            return self._register(
                run,
                name=f"{f.__module__}.{f.__qualname__}",
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
    ) -> Callable[[PollCallback], ActionTask]:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        def decorate(f: PollCallback) -> ActionTask:
            return self._register(
                f,
                name=f"{f.__module__}.{f.__qualname__}",
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
            token = uuid.uuid4()
            with SessionLocal.begin() as session:
                if not claim_task(session, x, token, expect=expect, during=during, duration=duration):
                    return

            def renew_lease() -> None:
                with SessionLocal.begin() as session:
                    if not renew_claim(session, x, token, during=during, duration=duration):
                        raise TranslationClaimLostError(f"Lost translation task claim: {x}")

            try:
                with SessionLocal.begin() as session:
                    task = session.execute(select(TranslationTask).where(TranslationTask.task_id == x)).scalar_one()
                    done = f(ActionTaskContext(db=session, task=task, claim_token=token, renew_lease=renew_lease))
                    finish_claim(
                        session,
                        x,
                        token,
                        during=during,
                        finish=finish if done else expect,
                        poll_interval=timedelta(seconds=interval_seconds) if not done else None,
                    )
            except Exception as error:
                with SessionLocal.begin() as session:
                    fail_claim(session, x, token, during=during, error=str(error))
                raise

            if not done:
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
        with SessionLocal.begin() as session:
            cur_task_q = (
                select(TranslationTask.batch_id, TranslationStage.job_id, TranslationStage.stage_num)
                .where(
                    TranslationTask.task_id == x,
                    TranslationTask.status == TranslationTaskStatus.COMPLETE,
                    TranslationTask.failed_at.is_(None),
                )
                .join(TranslationStage, TranslationTask.stage_id == TranslationStage.stage_id)
                .subquery()
            )
            tsa = aliased(TranslationStage)
            tta = aliased(TranslationTask)
            next_task = session.execute(
                select(tta.task_id, tsa.action)
                .select_from(cur_task_q)
                .join(tsa, (tsa.job_id == cur_task_q.c.job_id) & (tsa.stage_num == cur_task_q.c.stage_num + 1))
                .join(tta, (tta.batch_id == cur_task_q.c.batch_id) & (tta.stage_id == tsa.stage_id))
            ).one_or_none()
            if next_task is None:
                return
            next_task_id, next_action = next_task._t
            ready_task_id = session.scalar(
                update(TranslationTask)
                .where(
                    TranslationTask.task_id == next_task_id,
                    TranslationTask.status.in_((TranslationTaskStatus.WAITING, TranslationTaskStatus.READY)),
                    TranslationTask.failed_at.is_(None),
                    TranslationTask.claim_token.is_(None),
                )
                .values(status=TranslationTaskStatus.READY)
                .returning(TranslationTask.task_id)
            )
            if ready_task_id is None:
                return
        # A failed dispatch leaves the task READY so exitpoint can be retried.
        next_callbacks = self._callbacks_dict[TypeAdapter(ActionName).validate_python(next_action)]
        next_callbacks.entrypoint(next_task_id)
