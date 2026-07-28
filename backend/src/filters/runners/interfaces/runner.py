from typing import Protocol
from uuid import UUID

from src.schemas import Model


class Runner[InputT: Model](Protocol):
    def execute(self, job_id: UUID, input: InputT) -> None: ...
