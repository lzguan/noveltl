import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from src.autolabels.constants import MAX_MODEL_NAME_LEN, AutoLabelProgress, PromotionItemOutcome
from src.models import Base

if TYPE_CHECKING:
    from ..auth.models import User
    from ..novels.models import ChapterContent


class AutoLabelRun(Base):
    """
    Database model for a batch run of auto-labeling.

    A run groups autolabels created together in a single request, identified
    by the model and parameters used.

    Attributes:
        run_id: UUID identifier for this run.
        triggered_by: User who triggered the run. May be null for system-initiated runs.
        model_name: Name of the NER model used.
        model_params: Parameters for the NER model.
    """

    __tablename__ = "auto_label_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    novel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novels.novel_id", name="fk_auto_label_runs_novel_id_novels"), nullable=False
    )
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", name="fk_auto_label_runs_triggered_by_users"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(MAX_MODEL_NAME_LEN), nullable=False)
    model_params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    triggered_by_user: Mapped[User] = relationship(back_populates="autolabel_runs")
    autolabels_with_run: Mapped[list[AutoLabel]] = relationship(back_populates="run_of_autolabel")


class AutoLabel(Base):
    """
    Database model for storing automatically labeled data for a single chapter.

    Belongs to an AutoLabelRun, which carries the model name and parameters.

    Attributes:
        auto_label_id: UUID identifier for this AutoLabel.
        auto_label_data: JSONB column containing the auto-labeled data. Nullable (set after inference).
        auto_label_status: Status of labeling task for this autolabel.
        auto_label_last_job_id: Job id of last request to autogenerate this autolabel. Nullable.
        auto_label_message: Message about the status (e.g. failure reason). Nullable.
        chapter_content_id: UUID of chapter content this AutoLabel is associated with.
        run_id: UUID of the AutoLabelRun this autolabel belongs to.

    Notes:
        Each (chapter_content, run) pair is unique.
    """

    __tablename__ = "auto_labels"

    auto_label_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    auto_label_data: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    auto_label_status: Mapped[AutoLabelProgress] = mapped_column(
        Enum(AutoLabelProgress, native_enum=False, length=10, values_callable=lambda x: [str(e.value) for e in x]),
        nullable=False,
        default=AutoLabelProgress.PENDING,
    )
    auto_label_last_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True)
    auto_label_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    chapter_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapter_contents.chapter_content_id", name="fk_auto_labels_chapter_content_id_chapter_contents"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("auto_label_runs.run_id", name="fk_auto_labels_run_id_auto_label_runs"),
        nullable=False,
    )

    chapter_content_of_auto_label: Mapped[ChapterContent] = relationship(
        back_populates="auto_labels_with_chapter_content"
    )
    run_of_autolabel: Mapped[AutoLabelRun] = relationship(back_populates="autolabels_with_run")

    __table_args__ = (UniqueConstraint(chapter_content_id, run_id, name="uq_chapter_content_run_id"),)


class LabelPromotionJob(Base):
    """
    Database model for a background job copying an autolabel run's labels into a label group.

    Attributes:
        promotion_id: UUID identifier for this job.
        run_id: Autolabel run being promoted.
        label_group_id: Label group receiving the labels.
        requested_by: User who requested the promotion. Null if that user was deleted.
        start_chapter: Filter the job was requested with: least chapter number to include.
        end_chapter: Filter the job was requested with: greatest chapter number to include.
        chapter_ids: Filter the job was requested with: chapters to include, as a JSON list of UUIDs.
        status: Job status: pending, processing, done or failed.
        message: Reason the whole job failed. Nullable.
        claim_token: Token of the worker currently holding the job. Null when unclaimed.
        claim_expires_at: When the current claim lapses and the job may be reclaimed.
    """

    __tablename__ = "label_promotion_jobs"

    promotion_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("auto_label_runs.run_id", name="fk_label_promotion_jobs_run_id_auto_label_runs", ondelete="CASCADE"),
        nullable=False,
    )
    label_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "label_groups.label_group_id",
            name="fk_label_promotion_jobs_label_group_id_label_groups",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.user_id", name="fk_label_promotion_jobs_requested_by_users", ondelete="SET NULL"),
        nullable=True,
    )
    start_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[AutoLabelProgress] = mapped_column(
        Enum(
            AutoLabelProgress,
            native_enum=False,
            length=10,
            values_callable=lambda x: [str(e.value) for e in x],
            name="label_promotion_job_status",
        ),
        nullable=False,
        server_default=AutoLabelProgress.PENDING.value,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_token: Mapped[uuid.UUID | None] = mapped_column(UUID, nullable=True, unique=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(claim_token IS NULL AND claim_expires_at IS NULL) OR "
            "(claim_token IS NOT NULL AND claim_expires_at IS NOT NULL)",
            name="ck_label_promotion_jobs_claim_token_expiration",
        ),
        Index("ix_label_promotion_jobs_label_group_id", "label_group_id"),
        Index(
            "uq_label_promotion_jobs_active_run_group",
            "run_id",
            "label_group_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'processing')"),
        ),
    )


class LabelPromotionJobItem(Base):
    """
    Database model for one chapter selected for a promotion job when the job was created.

    Membership and position are fixed at creation; the outcome is written once when the item is processed.

    Attributes:
        promotion_id: Job this item belongs to.
        auto_label_id: Autolabel whose labels are promoted; it fixes the chapter content version they apply to.
        position: Processing order within the job.
        outcome: Null until processed, then done or failed.
        message: Reason the item failed. Nullable.
    """

    __tablename__ = "label_promotion_job_items"

    promotion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "label_promotion_jobs.promotion_id",
            name="fk_label_promotion_job_items_promotion_id_label_promotion_jobs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    auto_label_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "auto_labels.auto_label_id",
            name="fk_label_promotion_job_items_auto_label_id_auto_labels",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[PromotionItemOutcome | None] = mapped_column(
        Enum(
            PromotionItemOutcome,
            native_enum=False,
            length=10,
            values_callable=lambda x: [str(e.value) for e in x],
            name="label_promotion_item_outcome",
        ),
        nullable=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("promotion_id", "position", name="uq_label_promotion_job_items_promotion_position"),
        CheckConstraint(
            "message IS NULL OR outcome = 'failed'", name="ck_label_promotion_job_items_message_only_on_failure"
        ),
        Index(
            "ix_label_promotion_job_items_unprocessed",
            "promotion_id",
            "position",
            postgresql_where=text("outcome IS NULL"),
        ),
    )
