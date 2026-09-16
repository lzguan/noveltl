"""Worker-side task registration; imports the runner implementation."""

import logging
from uuid import UUID

from src.filters.celery_app import app
from src.filters.schemas import runner_input_adapter
from src.filters.task_names import RUN_RUNNER_TASK
from src.filters.worker.tasks import run_runner

logger = logging.getLogger(__name__)


@app.task(name=RUN_RUNNER_TASK, soft_time_limit=600, time_limit=660)
def run_runner_task(job_id: str, payload: dict[str, object]) -> None:
    runner_input = runner_input_adapter.validate_python(payload)
    run_runner(UUID(job_id), runner_input)
