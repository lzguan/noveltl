import uuid
from dataclasses import dataclass, field
from typing import Any

from src.autolabels.params import NERParams
from src.labels.schemas import LabelBase


@dataclass
class RecordingDispatcher:
    """In-memory dispatcher for tests that do not exercise Celery."""

    jobs: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    enqueue_error: Exception | None = None

    def enqueue(self, job_id: uuid.UUID, auto_label_id: uuid.UUID) -> None:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        self.jobs.append((job_id, auto_label_id))

    async def aenqueue(self, job_id: uuid.UUID, auto_label_id: uuid.UUID) -> None:
        self.enqueue(job_id, auto_label_id)


class DeterministicNERModel:
    """Cheap model double used when tests exercise worker plumbing."""

    model_name = "cluener"
    is_deterministic = True

    def predict(self, text: str, params: NERParams) -> tuple[list[LabelBase], Any]:
        del params
        if not text:
            return [], None
        return [
            LabelBase(
                label_entity_group="TEST",
                label_score=1.0,
                label_word=text[0],
                label_start=0,
                label_end=1,
                label_dirty=False,
            )
        ], None
