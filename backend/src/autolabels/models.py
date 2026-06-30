import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import Base
from .constants import MAX_MODEL_NAME_LEN, AutoLabelProgress

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

    run_id: Mapped[uuid.UUID] = mapped_column(postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid())
    novel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("novels.novel_id", name="fk_auto_label_runs_novel_id_novels"), nullable=False
    )
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", name="fk_auto_label_runs_triggered_by_users"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(MAX_MODEL_NAME_LEN), nullable=False)
    model_params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    triggered_by_user: Mapped["User"] = relationship(back_populates="autolabel_runs")
    autolabels_with_run: Mapped[list["AutoLabel"]] = relationship(back_populates="run_of_autolabel")


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

    auto_label_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    auto_label_data: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    auto_label_status: Mapped[AutoLabelProgress] = mapped_column(
        Enum(AutoLabelProgress, native_enum=False, length=10, values_callable=lambda x: [str(e.value) for e in x]),
        nullable=False,
        default=AutoLabelProgress.PENDING,
    )
    auto_label_last_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    auto_label_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    chapter_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapter_contents.chapter_content_id", name="fk_auto_labels_chapter_content_id_chapter_contents"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("auto_label_runs.run_id", name="fk_auto_labels_run_id_auto_label_runs"),
        nullable=False,
    )

    chapter_content_of_auto_label: Mapped["ChapterContent"] = relationship(
        back_populates="auto_labels_with_chapter_content"
    )
    run_of_autolabel: Mapped["AutoLabelRun"] = relationship(back_populates="autolabels_with_run")

    __table_args__ = (UniqueConstraint(chapter_content_id, run_id, name="uq_chapter_content_run_id"),)
