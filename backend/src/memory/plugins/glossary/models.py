from uuid import UUID

from sqlalchemy import Enum, ForeignKeyConstraint, Index, PrimaryKeyConstraint, UniqueConstraint, func, types
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.plugins.glossary.types import TermKind
from src.memory.types import ReviewStatus
from src.models import Base


class GlossaryTermFields:
    term_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False, server_default=func.gen_random_uuid())
    term: Mapped[str] = mapped_column(types.String(100), nullable=False)
    term_kind: Mapped[TermKind | None] = mapped_column(
        Enum(TermKind, native_enum=False, length=20, values_callable=lambda values: [value.value for value in values]),
        nullable=True,
    )
    memory_group_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus, native_enum=False, length=10, values_callable=lambda values: [value.value for value in values]
        ),
        nullable=False,
        default=ReviewStatus.PENDING,
        server_default=ReviewStatus.PENDING.value,
    )


class GlossaryTerm(GlossaryTermFields, Base):
    __tablename__ = "glossaries"

    __table_args__ = (
        PrimaryKeyConstraint("term_id"),
        ForeignKeyConstraint(
            ["memory_group_id"], ["memory_groups.memory_group_id"], name="fk_glossaries_memory_group_id_memory_groups"
        ),
        UniqueConstraint(
            "memory_group_id",
            "term",
            name="uq_glossaries_term_memory_group_id",
        ),
    )


class GlossaryAssociationFields:
    term_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False)
    memory_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False)


class GlossaryAssociation(GlossaryAssociationFields, Base):
    __tablename__ = "glossary_associations"

    __table_args__ = (
        PrimaryKeyConstraint("term_id", "memory_id"),
        ForeignKeyConstraint(
            ["term_id"], ["glossaries.term_id"], name="fk_glossary_associations_term_id_glossaries", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["memory_id"],
            ["memories.memory_id"],
            name="fk_glossary_associations_memory_id_memories",
            ondelete="CASCADE",
        ),
        Index("ix_glossary_associations_memory_id", "memory_id"),
    )
