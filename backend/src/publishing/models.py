import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UUID

from src.model_base import Base


class PublishingTarget(Base):
    __tablename__ = "publishing_targets"

    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    api_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    public_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "users.user_id",
            name="fk_publishing_targets_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserPublishingTarget(Base):
    __tablename__ = "user_publishing_targets"

    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "publishing_targets.target_id",
            name="fk_user_publishing_targets_target_id_publishing_targets",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "users.user_id",
            name="fk_user_publishing_targets_user_id_users",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'publisher')", name="ck_user_publishing_targets_role"),
        Index("ix_user_publishing_targets_user_id", "user_id"),
    )


class PublishJob(Base):
    __tablename__ = "publish_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID, primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    novel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novels.novel_id", name="fk_publish_jobs_novel_id_novels", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publishing_targets.target_id", name="fk_publish_jobs_target_id_publishing_targets", ondelete="CASCADE"),
        nullable=False,
    )
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "users.user_id",
            name="fk_publish_jobs_initiated_by_user_id_users",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default=sa.text("'pending'"))
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    start_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    include_novel_metadata: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa.text("true")
    )
    cursor_chapter_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_chapters: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sa.text("0"))
    synced_chapters: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=sa.text("0"))
    reader_novel_id: Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True)
    public_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_publish_jobs_status",
        ),
        CheckConstraint("mode IN ('all', 'outdated', 'range')", name="ck_publish_jobs_mode"),
        Index(
            "uq_publish_jobs_active_novel_target",
            "novel_id",
            "target_id",
            unique=True,
            postgresql_where=sa.text("status IN ('pending', 'processing')"),
        ),
        Index("ix_publish_jobs_novel_id_created_at", "novel_id", "created_at"),
    )
