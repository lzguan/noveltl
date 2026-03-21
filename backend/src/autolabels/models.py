import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import Base
from .constants import MAX_MODEL_NAME_LEN, AutoLabelProgress

if TYPE_CHECKING:
    from src.novels.models import RevisionText

class AutoLabel(Base):
    """
    Database model for storing automatically labeled data.

    Attributes:
        auto_label_id: Integer identifier for this AutoLabel.
        auto_label_data: JSONB column containing the auto-labeled data. Optional parameter.
        auto_label_model_name: Name of the model used to generate the auto labels.
        auto_label_model_params: Parameters used for the model to generate the auto labels.
        auto_label_status: Status of labeling task for this autolabel
        auto_label_last_job_id: Job id of last request to autogenerate this autolabel. Optional parameter.
        auto_label_message: Message about the status of this auto label (e.g. auto label failure reason). Optional parameter.
        revision_text_id: UUID of chapter revision text this AutoLabel is associated with.

    Notes:
        Each revision can only have one autolabel with a given model and parameters.
    """
    __tablename__ = 'auto_labels'

    auto_label_id : Mapped[int] = mapped_column(primary_key=True)
    auto_label_data : Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    auto_label_model_name : Mapped[str] = mapped_column(String(MAX_MODEL_NAME_LEN), nullable=False)
    auto_label_model_params : Mapped[dict[Any, Any]] = mapped_column(JSONB, nullable=False)
    auto_label_status : Mapped[AutoLabelProgress] = mapped_column(Enum(AutoLabelProgress, native_enum=False, length=10, values_callable=lambda x : [str(e.value) for e in x]), nullable=False, default=AutoLabelProgress.PENDING) # type: ignore
    auto_label_last_job_id : Mapped[str] = mapped_column(String(36), nullable=True)
    auto_label_message : Mapped[str] = mapped_column(Text, nullable=True)

    revision_text_id : Mapped[uuid.UUID] = mapped_column(ForeignKey('revision_texts.revision_text_id', name='fk_auto_labels_revision_text_id_revision_texts'), nullable=False)
    revision_text_of_auto_label : Mapped["RevisionText"] = relationship(back_populates='auto_labels_with_revision_text')

    __table_args__ = (
        UniqueConstraint(revision_text_id, auto_label_model_name, auto_label_model_params, name="uq_model_name_params"),

    )
