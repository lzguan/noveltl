import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, func, types
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.types import Creator, JobStatus, MemoryType, ReviewStatus
from src.models import Base


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


class Memory(Base):
    __tablename__ = "memories"

    memory_id: Mapped[uuid.UUID] = mapped_column(types.UUID, primary_key=True, server_default=func.gen_random_uuid())
    memory_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "memory_groups.memory_group_id",
            name="fk_memories_memory_group_id_memory_groups",
        ),
        nullable=False,
    )
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(
            MemoryType,
            native_enum=False,
            length=10,
            values_callable=lambda values: [use_case.value for use_case in values],
        ),
        nullable=False,
    )
    memory_observed_in: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapter_contents.chapter_content_id", ondelete="CASCADE"), nullable=False
    )
    memory_start_num: Mapped[int] = mapped_column(types.Integer, nullable=False)
    memory_end_num: Mapped[int | None] = mapped_column(types.Integer, nullable=True)
    supersedes_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memories.memory_id", ondelete="SET NULL"), nullable=True
    )
    memory_content: Mapped[str] = mapped_column(types.Text, nullable=False)
    memory_review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus,
            native_enum=False,
            length=10,
            values_callable=lambda values: [use_case.value for use_case in values],
        ),
        nullable=False,
        server_default="pending",
    )
    creator_type: Mapped[Creator] = mapped_column(
        Enum(
            Creator,
            native_enum=False,
            length=10,
            values_callable=lambda values: [use_case.value for use_case in values],
        ),
        nullable=False,
    )
    plugin_name: Mapped[str] = mapped_column(types.String(32), nullable=False)

    __table_args__ = (
        CheckConstraint("memory_start_num < memory_end_num", name="ck_memories_start_end_num"),
        Index("ix_memories_memory_group_id_start_num", "memory_group_id", "memory_start_num"),
        Index("ix_memories_memory_observed_in", "memory_observed_in"),
        Index("ix_memories_supersedes_memory_id", "supersedes_memory_id"),
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
        ),
        nullable=False,
    )
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
