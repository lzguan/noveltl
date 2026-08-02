import asyncio
import logging
from uuid import UUID

from src.filters.celery_app import app
from src.filters.dispatch.dispatcher import RunnerDispatcher
from src.filters.exceptions import RunnerEnqueueFailedException
from src.filters.schemas import RunnerInput, runner_input_adapter
from src.filters.worker.tasks import run_runner

logger = logging.getLogger(__name__)


@app.task(soft_time_limit=600, time_limit=660)
def run_runner_task(job_id: str, payload: dict[str, object]) -> None:
    runner_input = runner_input_adapter.validate_python(payload)
    run_runner(UUID(job_id), runner_input)


class CeleryRunnerDispatcher(RunnerDispatcher):
    """
    A dispatcher that enqueues runner requests to a Celery queue.
    """

    def enqueue(
        self,
        job_id: UUID,
        input: RunnerInput,
    ) -> None:
        """
        Enqueue a request.

        Args:
            job_id: String id to queue job with.
            input: Input for the runner.

        Raises:
            RunnerEnqueueFailedException: The runner task could not be published.
        """
        payload: dict[str, object] = input.model_dump(
            mode="json",
            by_alias=True,
            exclude_computed_fields=True,
        )
        try:
            logger.info("Enqueuing filter runner job job_id=%s runner=%s", job_id, input.runner_name)
            run_runner_task.apply_async((str(job_id), payload), task_id=str(job_id))
        except Exception as e:
            logger.exception("Filter runner enqueue failed job_id=%s runner=%s", job_id, input.runner_name)
            raise RunnerEnqueueFailedException(f"Celery enqueue failed: {e}") from e

    async def aenqueue(
        self,
        job_id: UUID,
        input: RunnerInput,
    ) -> None:
        """
        Enqueue a request.

        Args:
            job_id: String id to queue job with.
            input: Input for the runner.

        Raises:
            RunnerEnqueueFailedException: The runner task could not be published.
        """
        await asyncio.to_thread(self.enqueue, job_id, input)
