"""Task schedules: which task a job runs next and what each task waits for.

A schedule returns composable queries rather than results, so callers can embed
them in single atomic statements (e.g. claiming with claim-ownership checks).

Invariant: the task selected by ``next_unfinished`` never has unfinished
prerequisites. Otherwise workers would claim work that direct runs refuse.
"""

import uuid
from typing import Any, Protocol

from sqlalchemy import Exists, Select, SQLColumnExpression, select
from sqlalchemy.orm import aliased

from src.memory.agent.config import JobParams
from src.memory.models import MemoryChapterTask
from src.memory.types import JobStatus
from src.novels.models import Chapter


class TaskSchedule(Protocol):
    def run_order(self) -> tuple[SQLColumnExpression[Any], ...]:
        """ORDER BY terms listing a job's tasks in the order they run.

        Queries using them must join ``Chapter`` on the task's chapter.
        """
        ...

    def next_unfinished(self, memory_job_id: uuid.UUID) -> Select[uuid.UUID, int]:
        """Select the key (chapter_id, stage_num) of the job's next unfinished task.

        Failures count as unfinished, so a failed task blocks the schedule until
        it is explicitly retried rather than being skipped.
        """
        ...

    def unfinished_prerequisites(self, memory_job_id: uuid.UUID, chapter_id: uuid.UUID, stage_num: int) -> Exists:
        """Whether any task the given task waits for is unfinished."""
        ...


class StageBarrierSchedule:
    """Stages run as job-wide barriers; chapters run in order within a stage."""

    def run_order(self) -> tuple[SQLColumnExpression[Any], ...]:
        return (MemoryChapterTask.stage_num, Chapter.chapter_num, MemoryChapterTask.chapter_id)

    def next_unfinished(self, memory_job_id: uuid.UUID) -> Select[uuid.UUID, int]:
        return (
            select(MemoryChapterTask.chapter_id, MemoryChapterTask.stage_num)
            .join(Chapter, Chapter.chapter_id == MemoryChapterTask.chapter_id)
            .where(
                MemoryChapterTask.memory_job_id == memory_job_id,
                MemoryChapterTask.task_status != JobStatus.COMPLETED,
            )
            .order_by(*self.run_order())
            .limit(1)
        )

    def unfinished_prerequisites(self, memory_job_id: uuid.UUID, chapter_id: uuid.UUID, stage_num: int) -> Exists:
        # Every lower-stage task in the job; chapter order within a stage is not enforced.
        prerequisite = aliased(MemoryChapterTask)
        return (
            select(prerequisite.memory_job_id)
            .where(
                prerequisite.memory_job_id == memory_job_id,
                prerequisite.stage_num < stage_num,
                prerequisite.task_status != JobStatus.COMPLETED,
            )
            .exists()
        )


def get_schedule(params: JobParams) -> TaskSchedule:
    """Choose a job's schedule. Every current params version uses stage barriers."""
    return StageBarrierSchedule()
