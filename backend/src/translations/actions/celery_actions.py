import uuid

from celery import Celery
from celery.app import Task
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import aliased

from src.autolabels.worker.config import SessionLocal
from src.translations.actions.actions import ActionCallback, ActionCallbacks
from src.translations.models import TranslationStage, TranslationTask
from src.translations.types import ActionName


class CeleryActionCallbacks(ActionCallbacks):
    def __init__(self, celery_app: Celery, callbacks_dict: dict[ActionName, ActionCallbacks]) -> None:
        self.celery_app = celery_app
        self._intermediate: list[Task] = []
        self._callbacks_dict = callbacks_dict

    def new_func(self, f: ActionCallback) -> ActionCallback:
        idx = len(self._intermediate)

        def new_func(x: uuid.UUID) -> None:
            f(x)
            if idx + 1 < len(self._intermediate):
                self._intermediate[idx + 1].apply_async((x,))
            elif idx + 1 == len(self._intermediate):
                self.exitpoint(x)

        @self.celery_app.task
        def celery_task(x: uuid.UUID) -> None:
            new_func(x)

        self._intermediate.append(celery_task)

        return celery_task

    def entrypoint(self, x: uuid.UUID) -> None:
        if self._intermediate:
            self._intermediate[0].apply_async((x,))
        else:
            self.exitpoint(x)

    def exitpoint(self, x: uuid.UUID) -> None:
        with SessionLocal() as session:
            cur_task_q = (
                select(TranslationTask.batch_id, TranslationStage.job_id, TranslationStage.stage_num)
                .where(TranslationTask.task_id == x)
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
            next_callbacks = self._callbacks_dict[TypeAdapter(ActionName).validate_python(next_action)]
            next_callbacks.entrypoint(next_task_id)
