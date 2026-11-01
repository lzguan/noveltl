"""Version memory jobs, add chapter stages, and store canonical term translations.

Revision ID: d27e3f4a5b60
Revises: aa638b86e216
"""

import sqlalchemy as sa

from alembic import op

revision = "d27e3f4a5b60"
down_revision = "aa638b86e216"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE memory_jobs SET job_params = job_params || '{\"version\": 1}'::jsonb WHERE NOT job_params ? 'version'"
    )
    op.add_column("memory_chapter_tasks", sa.Column("stage_num", sa.Integer(), nullable=False, server_default="0"))
    # Defaults backfill legacy rows only; every new task must specify its stage.
    op.alter_column("memory_chapter_tasks", "stage_num", server_default=None)
    op.drop_constraint("memory_chapter_tasks_pkey", "memory_chapter_tasks", type_="primary")
    op.create_primary_key(
        "memory_chapter_tasks_pkey", "memory_chapter_tasks", ["memory_job_id", "chapter_id", "stage_num"]
    )

    op.create_table(
        "term_translations",
        sa.Column("term_id", sa.UUID(), nullable=False),
        sa.Column("translation", sa.Text(), nullable=False),
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
        sa.CheckConstraint("char_length(btrim(translation)) > 0", name="ck_term_translations_nonblank"),
        sa.ForeignKeyConstraint(
            ["term_id"], ["glossaries.term_id"], name="fk_term_translations_term_id_glossaries", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("term_id"),
    )


def downgrade():
    # V2 jobs cannot be represented by the old runner. Refuse to discard work.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM memory_jobs WHERE job_params->>'version' = '2')")):
        raise RuntimeError("Remove or export version 2 memory jobs before downgrading")
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM term_translations)")):
        raise RuntimeError("Remove or export term translations before downgrading")
    op.drop_table("term_translations")
    op.drop_constraint("memory_chapter_tasks_pkey", "memory_chapter_tasks", type_="primary")
    op.drop_column("memory_chapter_tasks", "stage_num")
    op.create_primary_key("memory_chapter_tasks_pkey", "memory_chapter_tasks", ["memory_job_id", "chapter_id"])
    op.execute("UPDATE memory_jobs SET job_params = job_params - 'version' WHERE job_params->>'version' = '1'")
