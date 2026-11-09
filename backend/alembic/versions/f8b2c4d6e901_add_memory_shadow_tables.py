import sqlalchemy as sa

from alembic import op

revision = "f8b2c4d6e901"
down_revision = "bc3dd7ebd17e"
branch_labels = None
depends_on = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def _shadow_columns():
    return [
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
        sa.ForeignKeyConstraint(["workspace_id"], ["memory_workspaces.workspace_id"], ondelete="CASCADE"),
    ]


def _review_status(name="review_status"):
    return sa.Column(
        name,
        sa.Enum("pending", "approved", "rejected", name="reviewstatus", native_enum=False, length=10),
        nullable=False,
        server_default="pending",
    )


def _creator():
    return sa.Column(
        "creator_type",
        sa.Enum("user", "workflow", "agent", name="creator", native_enum=False, length=10),
        nullable=False,
    )


def upgrade():
    op.create_table(
        "memory_workspaces",
        sa.Column("workspace_id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("memory_job_id", sa.UUID(), nullable=False),
        sa.Column("chapter_id", sa.UUID(), nullable=False),
        sa.Column("stage_num", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("workspace_id"),
        sa.ForeignKeyConstraint(
            ["memory_job_id", "chapter_id", "stage_num"],
            ["memory_chapter_tasks.memory_job_id", "memory_chapter_tasks.chapter_id", "memory_chapter_tasks.stage_num"],
            name="fk_memory_workspaces_task",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("stage_num >= 0", name="ck_memory_workspaces_stage_nonnegative"),
    )
    op.create_table(
        "shadow_memories",
        sa.Column("memory_id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("memory_group_id", sa.UUID(), nullable=False),
        sa.Column(
            "memory_type",
            sa.Enum("fact", "event", "def", "rel", "summary", name="memorytype", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("mark", sa.String(), nullable=True),
        sa.Column("memory_observed_in", sa.UUID(), nullable=False),
        sa.Column("memory_start_num", sa.Integer(), nullable=False),
        sa.Column("memory_end_num", sa.Integer(), nullable=True),
        sa.Column("supersedes_memory_id", sa.UUID(), nullable=True),
        sa.Column("memory_content", sa.Text(), nullable=False),
        _review_status("memory_review_status"),
        _creator(),
        sa.Column("plugin_name", sa.String(32), nullable=False),
        *_shadow_columns(),
        sa.PrimaryKeyConstraint("workspace_id", "memory_id"),
        sa.ForeignKeyConstraint(["memory_group_id"], ["memory_groups.memory_group_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memory_observed_in"], ["chapter_contents.chapter_content_id"], ondelete="CASCADE"),
        sa.CheckConstraint("memory_start_num < memory_end_num", name="ck_shadow_memories_start_end_num"),
    )
    op.create_index(
        "uq_shadow_continuity_summary",
        "shadow_memories",
        ["workspace_id", "memory_group_id", "memory_observed_in"],
        unique=True,
        postgresql_where=sa.text("memory_type = 'summary' AND plugin_name = 'continuity' AND NOT deleted"),
    )
    op.create_table(
        "shadow_terms",
        sa.Column("term_id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("term", sa.String(100), nullable=False),
        sa.Column(
            "term_kind",
            sa.Enum(
                "person",
                "place",
                "organization",
                "technique",
                "item",
                "concept",
                "title",
                "species",
                "other",
                name="termkind",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("memory_group_id", sa.UUID(), nullable=False),
        _review_status(),
        *_shadow_columns(),
        sa.PrimaryKeyConstraint("workspace_id", "term_id"),
        sa.ForeignKeyConstraint(["memory_group_id"], ["memory_groups.memory_group_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "uq_shadow_terms_workspace_group_term",
        "shadow_terms",
        ["workspace_id", "memory_group_id", "term"],
        unique=True,
        postgresql_where=sa.text("NOT deleted"),
    )
    op.create_table(
        "shadow_glossary_associations",
        sa.Column("term_id", sa.UUID(), nullable=False),
        sa.Column("memory_id", sa.UUID(), nullable=False),
        *_shadow_columns(),
        sa.PrimaryKeyConstraint("workspace_id", "term_id", "memory_id"),
    )
    op.create_index(
        "ix_shadow_associations_workspace_memory", "shadow_glossary_associations", ["workspace_id", "memory_id"]
    )
    op.create_table(
        "shadow_term_translations",
        sa.Column("term_id", sa.UUID(), nullable=False),
        sa.Column("translation", sa.Text(), nullable=False),
        _review_status(),
        _creator(),
        *_shadow_columns(),
        sa.PrimaryKeyConstraint("workspace_id", "term_id"),
        sa.CheckConstraint("char_length(btrim(translation)) > 0", name="ck_shadow_term_translations_nonblank"),
    )
    op.create_table(
        "shadow_conventions",
        sa.Column("convention_id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("memory_group_id", sa.UUID(), nullable=False),
        sa.Column(
            "category",
            sa.Enum("naming", "style", name="conventioncategory", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        _review_status(),
        _creator(),
        *_shadow_columns(),
        sa.PrimaryKeyConstraint("workspace_id", "convention_id"),
        sa.ForeignKeyConstraint(["memory_group_id"], ["memory_groups.memory_group_id"], ondelete="CASCADE"),
        sa.CheckConstraint("char_length(btrim(title)) > 0", name="ck_shadow_conventions_title_nonblank"),
        sa.CheckConstraint("char_length(btrim(rule)) > 0", name="ck_shadow_conventions_rule_nonblank"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM memory_workspaces)")):
        raise RuntimeError("Discard or export memory workspaces before downgrading")
    op.drop_table("shadow_conventions")
    op.drop_table("shadow_term_translations")
    op.drop_table("shadow_glossary_associations")
    op.drop_table("shadow_terms")
    op.drop_table("shadow_memories")
    op.drop_table("memory_workspaces")
