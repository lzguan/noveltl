from typing import Protocol
from uuid import UUID

from pydantic import ConfigDict

from src.schemas import Model


class RunnerInputBase(Model):
    """Base class for runner input models."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runner_name: str
    runtime_name: str


class Runner[InputT: RunnerInputBase](Protocol):
    def execute(self, job_id: UUID, input: InputT) -> None: ...
