import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, func, types
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.types import Creator, MemoryType, ReviewStatus
from src.models import Base


class MemoryGroup(Base):
    __tablename__ = "memory_groups"

    memory_group_id: Mapped[uuid.UUID] = mapped_column(
        types.UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    memory_group_name: Mapped[str] = mapped_column(types.String(100), nullable=False)
    novel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "novels.novel_id",
            name="fk_memory_groups_novel_id_novels",
        ),
        nullable=False,
    )
    memory_language: Mapped[str] = mapped_column(
        ForeignKey(
            "languages.language_code",
            name="fk_memory_groups_language_code_languages",
        ),
        nullable=False,
    )


class Memory(Base):
    __tablename__ = "memories"

    memory_id: Mapped[uuid.UUID] = mapped_column(types.UUID, primary_key=True, server_default=func.gen_random_uuid())
    memory_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "memory_groups.memory_group_id",
            name="fk_memories_memory_group_id_memory_groups",
        ),
        nullable=False,
    )
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(
            MemoryType,
            native_enum=False,
            length=10,
            values_callable=lambda values: [use_case.value for use_case in values],
        ),
        nullable=False,
    )
    memory_observed_in: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chapter_contents.chapter_content_id"), nullable=False
    )
    memory_start_num: Mapped[int] = mapped_column(types.Integer, nullable=False)
    memory_end_num: Mapped[int | None] = mapped_column(types.Integer, nullable=True)
    supersedes_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memories.memory_id", ondelete="SET NULL"), nullable=True
    )
    memory_content: Mapped[str] = mapped_column(types.Text, nullable=False)
    memory_review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus,
            native_enum=False,
            length=10,
            values_callable=lambda values: [use_case.value for use_case in values],
        ),
        nullable=False,
        server_default="pending",
    )
    creator_type: Mapped[Creator] = mapped_column(
        Enum(
            Creator,
            native_enum=False,
            length=10,
            values_callable=lambda values: [use_case.value for use_case in values],
        ),
        nullable=False,
    )
    plugin_name: Mapped[str] = mapped_column(types.String(32), nullable=False)

    __table_args__ = (CheckConstraint("memory_start_num < memory_end_num", name="ck_memories_start_end_num"),)
