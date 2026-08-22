import uuid

from sqlalchemy import ForeignKey, UniqueConstraint, func, types
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.types import ReviewStatus
from src.models import Base


class GlossaryTerm(Base):
    __tablename__ = "glossaries"

    term_id: Mapped[uuid.UUID] = mapped_column(types.UUID, primary_key=True, server_default=func.gen_random_uuid())
    term: Mapped[str] = mapped_column(types.String(100), nullable=False)
    memory_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "memory_groups.memory_group_id",
            name="fk_glossaries_memory_group_id_memory_groups",
        ),
        nullable=False,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        types.Enum(
            ReviewStatus,
            native_enum=False,
            length=10,
            values_callable=lambda values: [use_case.value for use_case in values],
        ),
        nullable=False,
        default=ReviewStatus.PENDING,
        server_default=ReviewStatus.PENDING.value,
    )

    __table_args__ = (
        UniqueConstraint(
            "term",
            "memory_group_id",
            name="uq_glossaries_term_memory_group_id",
        ),
    )


class GlossaryAssociation(Base):
    __tablename__ = "glossary_associations"

    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "glossaries.term_id",
            name="fk_glossary_associations_term_id_glossaries",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "memories.memory_id",
            name="fk_glossary_associations_memory_id_memories",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
