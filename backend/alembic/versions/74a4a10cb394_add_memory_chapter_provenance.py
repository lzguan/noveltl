import sqlalchemy as sa

from alembic import op

revision = "74a4a10cb394"
down_revision = "a9d3e7c1b2f4"
branch_labels = None
depends_on = None

BASE_TABLES = ("glossaries", "term_translations", "translation_conventions")
SHADOW_TABLES = ("shadow_terms", "shadow_term_translations", "shadow_conventions")


def upgrade() -> None:
    for table in BASE_TABLES + SHADOW_TABLES:
        op.add_column(table, sa.Column("recorded_on", sa.UUID(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_recorded_on_chapter_contents",
            table,
            "chapter_contents",
            ["recorded_on"],
            ["chapter_content_id"],
            ondelete="SET NULL",
        )
    for table in BASE_TABLES:
        op.create_index(f"ix_{table}_recorded_on", table, ["recorded_on"])

    # Deleting a chapter unlinks its memories instead of deleting them.
    op.alter_column("memories", "memory_observed_in", nullable=True)
    op.alter_column("shadow_memories", "memory_observed_in", nullable=True)
    op.drop_constraint("memories_memory_observed_in_fkey", "memories", type_="foreignkey")
    op.create_foreign_key(
        "fk_memories_memory_observed_in_chapter_contents",
        "memories",
        "chapter_contents",
        ["memory_observed_in"],
        ["chapter_content_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_memories_memory_observed_in_chapter_contents", "memories", type_="foreignkey")
    op.create_foreign_key(
        "memories_memory_observed_in_fkey",
        "memories",
        "chapter_contents",
        ["memory_observed_in"],
        ["chapter_content_id"],
        ondelete="CASCADE",
    )
    op.alter_column("shadow_memories", "memory_observed_in", nullable=False)
    op.alter_column("memories", "memory_observed_in", nullable=False)
    for table in BASE_TABLES:
        op.drop_index(f"ix_{table}_recorded_on", table_name=table)
    for table in BASE_TABLES + SHADOW_TABLES:
        op.drop_constraint(f"fk_{table}_recorded_on_chapter_contents", table, type_="foreignkey")
        op.drop_column(table, "recorded_on")
