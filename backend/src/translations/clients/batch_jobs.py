from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import NewType, Protocol

BatchJobId = NewType("BatchJobId", str)
BatchOutputId = NewType("BatchOutputId", str)


@dataclass(frozen=True)
class BatchJobPending:
    """The provider has accepted the batch job but has not completed it."""


@dataclass(frozen=True)
class BatchJobComplete:
    """The provider completed the batch job and made its output available."""

    output_id: BatchOutputId


@dataclass(frozen=True)
class BatchJobFailed:
    """The provider batch job reached a terminal failure."""

    error: str


type BatchJobPoll = BatchJobPending | BatchJobComplete | BatchJobFailed


class BatchJobClient(Protocol):
    """Provider-neutral access to an asynchronous batch API.

    IDs must remain usable by a fresh client in another worker process.
    Transport errors raise exceptions; BatchJobFailed describes a terminal
    provider state, not a failed polling request.
    """

    def create_batch_job(self, content: Iterable[bytes]) -> BatchJobId:
        """Consume a possibly single-use input stream and create a provider job."""
        ...

    def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        """Return the provider batch job's current state."""
        ...

    def fetch_batch_output(self, output_id: BatchOutputId) -> Iterator[bytes]:
        """Stream output bytes; chunks need not align with JSONL line boundaries.

        Each call starts a new download so finalization can retry independently.
        """
        ...
