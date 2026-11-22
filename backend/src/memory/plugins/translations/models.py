from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKeyConstraint, Index, PrimaryKeyConstraint, types
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.types import Creator, ReviewStatus
from src.model_base import Base


class TermTranslationFields:
    term_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False)
    translation: Mapped[str] = mapped_column(types.Text, nullable=False)
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
    recorded_on: Mapped[UUID | None] = mapped_column(types.UUID, nullable=True)


class TermTranslation(TermTranslationFields, Base):
    """One current rendering per glossary term, in its memory group's language."""

    __tablename__ = "term_translations"

    __table_args__ = (
        PrimaryKeyConstraint("term_id"),
        ForeignKeyConstraint(
            ["term_id"], ["glossaries.term_id"], name="fk_term_translations_term_id_glossaries", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["recorded_on"],
            ["chapter_contents.chapter_content_id"],
            name="fk_term_translations_recorded_on_chapter_contents",
            ondelete="SET NULL",
        ),
        CheckConstraint("char_length(btrim(translation)) > 0", name="ck_term_translations_nonblank"),
        Index("ix_term_translations_recorded_on", "recorded_on"),
    )
