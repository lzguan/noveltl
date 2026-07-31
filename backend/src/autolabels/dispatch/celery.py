import asyncio
import logging
import uuid

from src.autolabels.celery_app import app
from src.autolabels.dispatch.dispatcher import AutoLabelDispatcher
from src.autolabels.exceptions import EnqueueFailedException
from src.autolabels.worker.tasks import autolabel_infer

logger = logging.getLogger(__name__)


@app.task(soft_time_limit=600, time_limit=660)
def celery_infer(job_id: uuid.UUID, auto_label_id: uuid.UUID) -> None:
    """
    Enqueue a request to the Celery queue.
    """
    autolabel_infer(job_id, auto_label_id)


class CeleryDispatcher(AutoLabelDispatcher):
    def enqueue(
        self,
        job_id: uuid.UUID,
        auto_label_id: uuid.UUID,
    ) -> None:
        try:
            logger.info("Enqueuing autolabel job job_id=%s auto_label_id=%s", job_id, auto_label_id)
            celery_infer.apply_async((job_id, auto_label_id), task_id=str(job_id))

        except Exception as e:
            logger.exception("Autolabel enqueue failed job_id=%s auto_label_id=%s", job_id, auto_label_id)
            raise EnqueueFailedException(f"Celery enqueue failed: {str(e)}") from e

    async def aenqueue(
        self,
        job_id: uuid.UUID,
        auto_label_id: uuid.UUID,
    ) -> None:
        await asyncio.to_thread(self.enqueue, job_id, auto_label_id)
