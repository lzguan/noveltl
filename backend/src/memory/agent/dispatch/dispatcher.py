from typing import Protocol
from uuid import UUID


class MemoryAgentDispatcher(Protocol):
    """Queue-independent interface for publishing memory-agent work."""

    async def aenqueue_job(self, memory_job_id: UUID) -> None:
        """Asynchronously publish a request to process a whole job."""
        ...

    async def aenqueue_task(self, memory_job_id: UUID, chapter_id: UUID, stage_num: int = 0) -> None:
        """Asynchronously publish a request to process one chapter task."""
        ...
