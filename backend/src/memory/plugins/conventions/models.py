from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKeyConstraint, Index, PrimaryKeyConstraint, func, types
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.types import Creator, ReviewStatus
from src.models import Base


class TranslationConventionFields:
    convention_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False, server_default=func.gen_random_uuid())
    memory_group_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False)
    category: Mapped[ConventionCategory] = mapped_column(
        Enum(
            ConventionCategory,
            native_enum=False,
            length=10,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(types.String(200), nullable=False)
    rule: Mapped[str] = mapped_column(types.Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(types.Text, nullable=True)
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


class TranslationConvention(TranslationConventionFields, Base):
    """Novel-level translation guidance for one memory group's target language.

    Conventions are global rules, not per-term data. Illustrative examples can be
    added later as a child table keyed by ``convention_id``; scoping to story arcs
    (e.g. quick-transmigration worlds) is deferred to a future arc concept.
    """

    __tablename__ = "translation_conventions"

    __table_args__ = (
        PrimaryKeyConstraint("convention_id"),
        ForeignKeyConstraint(
            ["memory_group_id"],
            ["memory_groups.memory_group_id"],
            name="fk_translation_conventions_memory_group_id_memory_groups",
        ),
        CheckConstraint("char_length(btrim(title)) > 0", name="ck_translation_conventions_title_nonblank"),
        CheckConstraint("char_length(btrim(rule)) > 0", name="ck_translation_conventions_rule_nonblank"),
        Index("ix_translation_conventions_memory_group_id", "memory_group_id"),
    )
