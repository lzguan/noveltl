from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    func,
    text,
    types,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary.types import TermKind
from src.memory.types import Creator, MemoryType, ReviewStatus
from src.models import Base


class MemoryWorkspace(Base):
    __tablename__ = "memory_workspaces"

    workspace_id: Mapped[UUID] = mapped_column(types.UUID, primary_key=True, server_default=func.gen_random_uuid())
    memory_job_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False)
    chapter_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False)
    stage_num: Mapped[int] = mapped_column(types.Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["memory_job_id", "chapter_id", "stage_num"],
            ["memory_chapter_tasks.memory_job_id", "memory_chapter_tasks.chapter_id", "memory_chapter_tasks.stage_num"],
            name="fk_memory_workspaces_task",
            ondelete="CASCADE",
        ),
        CheckConstraint("stage_num >= 0", name="ck_memory_workspaces_stage_nonnegative"),
    )


class ShadowRecord:
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_workspaces.workspace_id", ondelete="CASCADE"), primary_key=True
    )
    deleted: Mapped[bool] = mapped_column(types.Boolean, nullable=False, default=False, server_default="false")


class ShadowMemory(ShadowRecord, Base):
    __tablename__ = "shadow_memories"

    memory_id: Mapped[UUID] = mapped_column(types.UUID, primary_key=True, server_default=func.gen_random_uuid())
    memory_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_groups.memory_group_id", ondelete="CASCADE"), nullable=False
    )
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(
            MemoryType, native_enum=False, length=10, values_callable=lambda values: [value.value for value in values]
        ),
        nullable=False,
    )
    mark: Mapped[str | None] = mapped_column(types.String, nullable=True)
    memory_observed_in: Mapped[UUID] = mapped_column(
        ForeignKey("chapter_contents.chapter_content_id", ondelete="CASCADE"), nullable=False
    )
    memory_start_num: Mapped[int] = mapped_column(types.Integer, nullable=False)
    memory_end_num: Mapped[int | None] = mapped_column(types.Integer, nullable=True)
    supersedes_memory_id: Mapped[UUID | None] = mapped_column(types.UUID, nullable=True)
    memory_content: Mapped[str] = mapped_column(types.Text, nullable=False)
    memory_review_status: Mapped[ReviewStatus] = mapped_column(
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
    plugin_name: Mapped[str] = mapped_column(types.String(32), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("workspace_id", "memory_id"),
        CheckConstraint("memory_start_num < memory_end_num", name="ck_shadow_memories_start_end_num"),
        Index(
            "uq_shadow_continuity_summary",
            "workspace_id",
            "memory_group_id",
            "memory_observed_in",
            unique=True,
            postgresql_where=text("memory_type = 'summary' AND plugin_name = 'continuity' AND NOT deleted"),
        ),
    )


class ShadowTerm(ShadowRecord, Base):
    __tablename__ = "shadow_terms"

    term_id: Mapped[UUID] = mapped_column(types.UUID, primary_key=True, server_default=func.gen_random_uuid())
    term: Mapped[str] = mapped_column(types.String(100), nullable=False)
    term_kind: Mapped[TermKind | None] = mapped_column(
        Enum(TermKind, native_enum=False, length=20, values_callable=lambda values: [value.value for value in values]),
        nullable=True,
    )
    memory_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_groups.memory_group_id", ondelete="CASCADE"), nullable=False
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(
            ReviewStatus, native_enum=False, length=10, values_callable=lambda values: [value.value for value in values]
        ),
        nullable=False,
        default=ReviewStatus.PENDING,
        server_default=ReviewStatus.PENDING.value,
    )

    __table_args__ = (
        PrimaryKeyConstraint("workspace_id", "term_id"),
        Index(
            "uq_shadow_terms_workspace_group_term",
            "workspace_id",
            "memory_group_id",
            "term",
            unique=True,
            postgresql_where=text("NOT deleted"),
        ),
    )


class ShadowGlossaryAssociation(ShadowRecord, Base):
    __tablename__ = "shadow_glossary_associations"

    term_id: Mapped[UUID] = mapped_column(types.UUID, primary_key=True)
    memory_id: Mapped[UUID] = mapped_column(types.UUID, primary_key=True)

    __table_args__ = (
        PrimaryKeyConstraint("workspace_id", "term_id", "memory_id"),
        Index("ix_shadow_associations_workspace_memory", "workspace_id", "memory_id"),
    )


class ShadowTermTranslation(ShadowRecord, Base):
    __tablename__ = "shadow_term_translations"

    term_id: Mapped[UUID] = mapped_column(types.UUID, primary_key=True)
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

    __table_args__ = (
        PrimaryKeyConstraint("workspace_id", "term_id"),
        CheckConstraint("char_length(btrim(translation)) > 0", name="ck_shadow_term_translations_nonblank"),
    )


class ShadowConvention(ShadowRecord, Base):
    __tablename__ = "shadow_conventions"

    convention_id: Mapped[UUID] = mapped_column(types.UUID, primary_key=True, server_default=func.gen_random_uuid())
    memory_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_groups.memory_group_id", ondelete="CASCADE"), nullable=False
    )
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

    __table_args__ = (
        PrimaryKeyConstraint("workspace_id", "convention_id"),
        CheckConstraint("char_length(btrim(title)) > 0", name="ck_shadow_conventions_title_nonblank"),
        CheckConstraint("char_length(btrim(rule)) > 0", name="ck_shadow_conventions_rule_nonblank"),
    )
