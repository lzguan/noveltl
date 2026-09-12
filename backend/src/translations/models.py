import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID

from src.models import Base
from src.translations.types import TranslationTaskStatus


class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.novel_id"), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class TranslationStage(Base):
    __tablename__ = "translation_stages"

    stage_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("translation_jobs.job_id", ondelete="CASCADE"), nullable=False)
    stage_num: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("job_id", "stage_num", name="uq_translation_stage_job_num"),
        CheckConstraint("stage_num >= 0", name="ck_translation_stage_num"),
    )


class TranslationBatch(Base):
    __tablename__ = "translation_batches"

    batch_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("translation_jobs.job_id", ondelete="CASCADE"), nullable=False)
    batch_num: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("job_id", "batch_num", name="uq_translation_batch_job_num"),
        CheckConstraint("batch_num >= 0", name="ck_translation_batch_num"),
    )


class TranslationJobChapter(Base):
    __tablename__ = "translation_job_chapters"

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("translation_jobs.job_id", ondelete="CASCADE"), primary_key=True
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.chapter_id"), primary_key=True)
    source_chapter_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapter_contents.chapter_content_id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("translation_batches.batch_id", ondelete="CASCADE"), nullable=False, index=True
    )


class TranslationTask(Base):
    __tablename__ = "translation_tasks"

    task_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    stage_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("translation_stages.stage_id", ondelete="CASCADE"), nullable=False
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("translation_batches.batch_id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[TranslationTaskStatus] = mapped_column(
        Enum(
            TranslationTaskStatus,
            native_enum=False,
            length=10,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
    )
    input_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stored_files.file_id"), nullable=True)
    output_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stored_files.file_id"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("stage_id", "batch_id", name="uq_translation_task_stage_batch"),
    )
