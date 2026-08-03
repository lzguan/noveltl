from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from src.filters.schemas import RunnerInput


@dataclass
class RecordingRunnerDispatcher:
    """In-memory filter dispatcher with an optional enqueue observation hook."""

    jobs: list[tuple[UUID, RunnerInput]] = field(default_factory=list)
    enqueue_error: Exception | None = None
    on_enqueue: Callable[[UUID, RunnerInput], None] | None = None

    def enqueue(self, job_id: UUID, input: RunnerInput) -> None:
        if self.on_enqueue is not None:
            self.on_enqueue(job_id, input)
        if self.enqueue_error is not None:
            raise self.enqueue_error
        self.jobs.append((job_id, input))

    async def aenqueue(self, job_id: UUID, input: RunnerInput) -> None:
        self.enqueue(job_id, input)
