from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    func,
    text,
    types,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.memory.models import MemoryFields
from src.memory.plugins.conventions.models import TranslationConventionFields
from src.memory.plugins.glossary.models import GlossaryAssociationFields, GlossaryTermFields
from src.memory.plugins.translations.models import TermTranslationFields
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
    workspace_id: Mapped[UUID] = mapped_column(types.UUID, nullable=False)
    deleted: Mapped[bool] = mapped_column(types.Boolean, nullable=False, default=False, server_default="false")


class ShadowMemory(MemoryFields, ShadowRecord, Base):
    __tablename__ = "shadow_memories"

    __table_args__ = (
        ForeignKeyConstraint(["workspace_id"], ["memory_workspaces.workspace_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["memory_group_id"], ["memory_groups.memory_group_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["memory_observed_in"], ["chapter_contents.chapter_content_id"], ondelete="CASCADE"),
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


class ShadowTerm(GlossaryTermFields, ShadowRecord, Base):
    __tablename__ = "shadow_terms"

    __table_args__ = (
        ForeignKeyConstraint(["workspace_id"], ["memory_workspaces.workspace_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["memory_group_id"], ["memory_groups.memory_group_id"], ondelete="CASCADE"),
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


class ShadowGlossaryAssociation(GlossaryAssociationFields, ShadowRecord, Base):
    __tablename__ = "shadow_glossary_associations"

    __table_args__ = (
        ForeignKeyConstraint(["workspace_id"], ["memory_workspaces.workspace_id"], ondelete="CASCADE"),
        PrimaryKeyConstraint("workspace_id", "term_id", "memory_id"),
        Index("ix_shadow_associations_workspace_memory", "workspace_id", "memory_id"),
    )


class ShadowTermTranslation(TermTranslationFields, ShadowRecord, Base):
    __tablename__ = "shadow_term_translations"

    __table_args__ = (
        ForeignKeyConstraint(["workspace_id"], ["memory_workspaces.workspace_id"], ondelete="CASCADE"),
        PrimaryKeyConstraint("workspace_id", "term_id"),
        CheckConstraint("char_length(btrim(translation)) > 0", name="ck_shadow_term_translations_nonblank"),
    )


class ShadowConvention(TranslationConventionFields, ShadowRecord, Base):
    __tablename__ = "shadow_conventions"

    __table_args__ = (
        ForeignKeyConstraint(["workspace_id"], ["memory_workspaces.workspace_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["memory_group_id"], ["memory_groups.memory_group_id"], ondelete="CASCADE"),
        PrimaryKeyConstraint("workspace_id", "convention_id"),
        CheckConstraint("char_length(btrim(title)) > 0", name="ck_shadow_conventions_title_nonblank"),
        CheckConstraint("char_length(btrim(rule)) > 0", name="ck_shadow_conventions_rule_nonblank"),
    )
