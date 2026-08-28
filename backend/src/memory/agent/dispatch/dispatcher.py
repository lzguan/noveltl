from typing import Protocol
from uuid import UUID


class MemoryAgentDispatcher(Protocol):
    """Queue-independent interface for publishing memory-agent work."""

    def enqueue_job(self, memory_job_id: UUID) -> None:
        """Publish a request to process every pending task in a job."""
        ...

    def enqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        """Publish a request to process one pending chapter task."""
        ...

    async def aenqueue_job(self, memory_job_id: UUID) -> None:
        """Asynchronously publish a request to process a whole job."""
        ...

    async def aenqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        """Asynchronously publish a request to process one chapter task."""
        ...
