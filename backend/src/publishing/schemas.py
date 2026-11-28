import uuid
from datetime import datetime
from typing import Self

from pydantic import ConfigDict, Field, model_validator

from src.publishing.constants import PublishJobStatus, PublishMode, TargetRole
from src.schemas import Model


class CreatePublishingTarget(Model):
    name: str = Field(min_length=1, max_length=255)
    api_base_url: str = Field(min_length=1, max_length=2048)
    api_key: str = Field(min_length=1, max_length=1024)


class UpdatePublishingTarget(Model):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    api_base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_key: str | None = Field(default=None, min_length=1, max_length=1024)


class PublishingTargetRead(Model):
    target_id: uuid.UUID
    name: str
    api_base_url: str
    public_base_url: str | None
    key_prefix: str
    role: TargetRole
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class PublishingTargetTestResult(Model):
    ok: bool
    protocol_version: int
    name: str
    public_base_url: str


class PublishingTargetMemberRead(Model):
    user_id: uuid.UUID
    user_name: str
    role: TargetRole
    created_at: datetime


class UpsertPublishingTargetMember(Model):
    user_id: uuid.UUID | None = None
    user_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: TargetRole = "publisher"

    @model_validator(mode="after")
    def validate_user_identifier(self) -> Self:
        if (self.user_id is None) == (self.user_name is None):
            raise ValueError("Provide exactly one of userId or userName.")
        return self


class PublishJobRead(Model):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    novel_id: uuid.UUID
    target_id: uuid.UUID
    initiated_by_user_id: uuid.UUID | None
    status: PublishJobStatus
    mode: PublishMode
    start_chapter: int | None
    end_chapter: int | None
    include_novel_metadata: bool
    cursor_chapter_num: int | None
    total_chapters: int
    synced_chapters: int
    reader_novel_id: uuid.UUID | None
    public_url: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class NovelPublishStatus(Model):
    exists_on_reader: bool
    reader_novel_id: uuid.UUID | None
    public_url: str | None
    studio_chapter_count: int
    reader_chapter_count: int
    new_count: int
    outdated_count: int
    up_to_date_count: int
    reader_only_count: int
    active_job: PublishJobRead | None
    latest_job: PublishJobRead | None


class StartPublishRequest(Model):
    target_id: uuid.UUID
    mode: PublishMode = "outdated"
    start_chapter: int | None = Field(default=None, ge=0)
    end_chapter: int | None = Field(default=None, ge=0)
    include_novel_metadata: bool = True

    @model_validator(mode="after")
    def validate_mode_and_range(self) -> Self:
        if self.mode == "range":
            if self.start_chapter is None or self.end_chapter is None:
                raise ValueError("startChapter and endChapter are required when mode is 'range'.")
            if self.start_chapter > self.end_chapter:
                raise ValueError("startChapter must be less than or equal to endChapter.")
        elif self.start_chapter is not None or self.end_chapter is not None:
            raise ValueError("startChapter and endChapter are only allowed when mode is 'range'.")
        return self
