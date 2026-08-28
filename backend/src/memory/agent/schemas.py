from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from src.memory.agent.tasks.jobs import JobParams
from src.memory.types import JobStatus
from src.schemas import Model, Page


class CreateMemoryJob(Model):
    memory_group_id: UUID
    start_chapter_num: int | None = Field(default=None, ge=0)
    end_chapter_num: int | None = Field(default=None, ge=0)
    params: JobParams


class MemoryJob(Model):
    model_config = ConfigDict(from_attributes=True)

    memory_job_id: UUID
    memory_group_id: UUID
    job_params: JobParams
    claim_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MemoryChapterTaskCounts(Model):
    pending: int = Field(ge=0)
    processing: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)


class MemoryJobSummary(Model):
    job: MemoryJob
    task_counts: MemoryChapterTaskCounts
    is_claimed: bool


class MemoryJobSummaryList(Model):
    server_time: datetime
    summaries: list[MemoryJobSummary]


class MemoryJobSummarySnapshot(Model):
    server_time: datetime
    summary: MemoryJobSummary


class MemoryChapterTask(Model):
    memory_job_id: UUID
    chapter_id: UUID
    chapter_num: int
    task_status: JobStatus
    attempt_count: int
    created_at: datetime
    updated_at: datetime


MemoryChapterTaskPage = Page[MemoryChapterTask]
