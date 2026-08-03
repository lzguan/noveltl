from typing import Protocol
from uuid import UUID

from src.filters.schemas import RunnerInput


class RunnerDispatcher(Protocol):
    """
    Abstract class for enqueuing a runner request to some queue.
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
        ...

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
        ...
