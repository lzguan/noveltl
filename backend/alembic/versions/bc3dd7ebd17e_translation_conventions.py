"""Add translation conventions.

Revision ID: bc3dd7ebd17e
Revises: d27e3f4a5b60
"""

import sqlalchemy as sa

from alembic import op

revision = "bc3dd7ebd17e"
down_revision = "d27e3f4a5b60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "translation_conventions",
        sa.Column("convention_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("memory_group_id", sa.UUID(), nullable=False),
        sa.Column(
            "category",
            sa.Enum("naming", "style", name="conventioncategory", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.Enum("pending", "approved", "rejected", name="reviewstatus", native_enum=False, length=10),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "creator_type",
            sa.Enum("user", "workflow", "agent", name="creator", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("char_length(btrim(title)) > 0", name="ck_translation_conventions_title_nonblank"),
        sa.CheckConstraint("char_length(btrim(rule)) > 0", name="ck_translation_conventions_rule_nonblank"),
        sa.ForeignKeyConstraint(
            ["memory_group_id"],
            ["memory_groups.memory_group_id"],
            name="fk_translation_conventions_memory_group_id_memory_groups",
        ),
        sa.PrimaryKeyConstraint("convention_id"),
    )
    op.create_index("ix_translation_conventions_memory_group_id", "translation_conventions", ["memory_group_id"])


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM translation_conventions)")):
        raise RuntimeError("Remove or export translation conventions before downgrading")
    op.drop_index("ix_translation_conventions_memory_group_id", table_name="translation_conventions")
    op.drop_table("translation_conventions")
