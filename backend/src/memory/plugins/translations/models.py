from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.types import Creator, ReviewStatus
from src.models import Base


class TermTranslation(Base):
    """One current rendering per glossary term, in its memory group's language."""

    __tablename__ = "term_translations"

    term_id: Mapped[UUID] = mapped_column(
        ForeignKey("glossaries.term_id", name="fk_term_translations_term_id_glossaries", ondelete="CASCADE"),
        primary_key=True,
    )
    translation: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
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

    __table_args__ = (CheckConstraint("char_length(btrim(translation)) > 0", name="ck_term_translations_nonblank"),)
