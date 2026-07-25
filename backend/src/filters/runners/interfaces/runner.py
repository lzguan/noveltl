from typing import Protocol

from src.schemas import Model


class Runner[InputT: Model](Protocol):
    def execute(self, job_id: str, input: InputT) -> None: ...
