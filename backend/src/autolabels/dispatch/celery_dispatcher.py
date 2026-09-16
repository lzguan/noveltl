"""Publishing side of the autolabels queue; no inference implementation imports.

Work is published by task name through `send_task`, so an API process never
imports the inference implementation behind it. The worker registers the
matching name in `src.autolabels.dispatch.celery`.
"""

import asyncio
import logging
import uuid

from src.autolabels.celery_app import app
from src.autolabels.dispatch.dispatcher import AutoLabelDispatcher
from src.autolabels.exceptions import EnqueueFailedException
from src.autolabels.task_names import CELERY_INFER

logger = logging.getLogger(__name__)


class CeleryDispatcher(AutoLabelDispatcher):
    def enqueue(
        self,
        job_id: uuid.UUID,
        auto_label_id: uuid.UUID,
    ) -> None:
        try:
            logger.info("Enqueuing autolabel job job_id=%s auto_label_id=%s", job_id, auto_label_id)
            app.send_task(CELERY_INFER, args=(job_id, auto_label_id), task_id=str(job_id))

        except Exception as e:
            logger.exception("Autolabel enqueue failed job_id=%s auto_label_id=%s", job_id, auto_label_id)
            raise EnqueueFailedException(f"Celery enqueue failed: {str(e)}") from e

    async def aenqueue(
        self,
        job_id: uuid.UUID,
        auto_label_id: uuid.UUID,
    ) -> None:
        await asyncio.to_thread(self.enqueue, job_id, auto_label_id)
