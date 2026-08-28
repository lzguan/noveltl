from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class RecordingMemoryAgentDispatcher:
    """In-memory dispatcher for memory-agent service tests."""

    jobs: list[UUID] = field(default_factory=list)
    tasks: list[tuple[UUID, UUID]] = field(default_factory=list)
    enqueue_error: Exception | None = None

    def enqueue_job(self, memory_job_id: UUID) -> None:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        self.jobs.append(memory_job_id)

    def enqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        self.tasks.append((memory_job_id, chapter_id))

    async def aenqueue_job(self, memory_job_id: UUID) -> None:
        self.enqueue_job(memory_job_id)

    async def aenqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        self.enqueue_task(memory_job_id, chapter_id)
