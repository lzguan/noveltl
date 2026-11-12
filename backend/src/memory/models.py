import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    func,
    text,
    types,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.types import Creator, JobStatus, MemoryType, ReviewStatus
from src.model_base import Base


class MemoryGroup(Base):
    __tablename__ = "memory_groups"

    memory_group_id: Mapped[uuid.UUID] = mapped_column(
        types.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    memory_group_name: Mapped[str] = mapped_column(types.String(100), nullable=False)
    novel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "novels.novel_id",
            name="fk_memory_groups_novel_id_novels",
        ),
        nullable=False,
    )
    memory_language: Mapped[str] = mapped_column(
        ForeignKey(
            "languages.language_code",
            name="fk_memory_groups_language_code_languages",
        ),
        nullable=False,
    )

    __table_args__ = (Index("ix_memory_groups_novel_id", "novel_id"),)


class MemoryFields:
    memory_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False, server_default=func.gen_random_uuid())
    memory_group_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False)
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(
            MemoryType, native_enum=False, length=10, values_callable=lambda values: [value.value for value in values]
        ),
        nullable=False,
    )
    mark: Mapped[str | None] = mapped_column(types.String, nullable=True)
    memory_observed_in: Mapped[UUID] = mapped_column(types.UUID, nullable=False)
    memory_start_num: Mapped[int] = mapped_column(types.Integer, nullable=False)
    memory_end_num: Mapped[int | None] = mapped_column(types.Integer, nullable=True)
    supersedes_memory_id: Mapped[UUID | None] = mapped_column(types.UUID, nullable=True)
    memory_content: Mapped[str] = mapped_column(types.Text, nullable=False)
    memory_review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus, native_enum=False, length=10, values_callable=lambda values: [value.value for value in values]
        ),
        nullable=False,
        server_default=ReviewStatus.PENDING.value,
    )
    creator_type: Mapped[Creator] = mapped_column(
        Enum(Creator, native_enum=False, length=10, values_callable=lambda values: [value.value for value in values]),
        nullable=False,
    )
    plugin_name: Mapped[str] = mapped_column(types.String(32), nullable=False)


class Memory(MemoryFields, Base):
    __tablename__ = "memories"

    __table_args__ = (
        PrimaryKeyConstraint("memory_id"),
        ForeignKeyConstraint(
            ["memory_group_id"], ["memory_groups.memory_group_id"], name="fk_memories_memory_group_id_memory_groups"
        ),
        ForeignKeyConstraint(["memory_observed_in"], ["chapter_contents.chapter_content_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["supersedes_memory_id"], ["memories.memory_id"], ondelete="SET NULL"),
        CheckConstraint("memory_start_num < memory_end_num", name="ck_memories_start_end_num"),
        Index("ix_memories_memory_group_id_start_num", "memory_group_id", "memory_start_num"),
        Index("ix_memories_memory_observed_in", "memory_observed_in"),
        Index("ix_memories_supersedes_memory_id", "supersedes_memory_id"),
        Index(
            "uq_continuity_summary_group_content",
            "memory_group_id",
            "memory_observed_in",
            unique=True,
            postgresql_where=text("memory_type = 'summary' AND plugin_name = 'continuity'"),
        ),
    )


class MemoryJob(Base):
    __tablename__ = "memory_jobs"

    memory_job_id: Mapped[uuid.UUID] = mapped_column(
        types.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    memory_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "memory_groups.memory_group_id",
            name="fk_memory_jobs_memory_group_id_memory_groups",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    job_params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    claim_token: Mapped[uuid.UUID | None] = mapped_column(types.UUID, nullable=True, unique=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(types.DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(claim_token IS NULL AND claim_expires_at IS NULL) OR "
            "(claim_token IS NOT NULL AND claim_expires_at IS NOT NULL)",
            name="ck_memory_jobs_claim_token_expiration",
        ),
    )


class MemoryChapterTask(Base):
    __tablename__ = "memory_chapter_tasks"

    memory_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "memory_jobs.memory_job_id",
            name="fk_memory_job_tasks_memory_job_id_memory_jobs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "chapters.chapter_id",
            name="fk_memory_job_tasks_chapter_id_chapters",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    stage_num: Mapped[int] = mapped_column(types.Integer, primary_key=True)
    task_status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            native_enum=False,
            length=15,
            values_callable=lambda values: [use_case.value for use_case in values],
        ),
        nullable=False,
        server_default="pending",
    )
    attempt_count: Mapped[int] = mapped_column(types.Integer, nullable=False, server_default="0")
