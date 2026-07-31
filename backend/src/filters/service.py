from uuid import UUID

from src.filters.dispatch.tasks import run_runner_task
from src.filters.schemas import RunnerInput


def run_runner(input: RunnerInput, job_id: UUID) -> None:
    """Run the appropriate runner based on the input type."""
    run_runner_task.apply_async((job_id, input), task_id=str(job_id))
