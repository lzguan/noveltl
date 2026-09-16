"""Worker-side task registration; imports the inference implementation."""

import uuid

from src.autolabels.celery_app import app
from src.autolabels.task_names import CELERY_INFER
from src.autolabels.worker.tasks import autolabel_infer


@app.task(name=CELERY_INFER, soft_time_limit=600, time_limit=660)
def celery_infer(job_id: uuid.UUID, auto_label_id: uuid.UUID) -> None:
    """
    Enqueue a request to the Celery queue.
    """
    autolabel_infer(job_id, auto_label_id)
