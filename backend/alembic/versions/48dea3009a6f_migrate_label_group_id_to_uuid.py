"""migrate label_group_id to uuid

Revision ID: 48dea3009a6f
Revises: 4df7e746c509
Create Date: 2026-03-22 03:59:52.003847+00:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "48dea3009a6f"
down_revision = "4df7e746c509"
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. drop FK constraints referencing label_groups.label_group_id ---

    op.drop_constraint("fk_label_datas_label_group_id_label_groups", "label_datas", type_="foreignkey")
    op.drop_constraint("label_group_contributors_label_group_id_fkey", "label_group_contributors", type_="foreignkey")

    # --- 2. drop unique/composite constraints that include label_group_id ---

    op.drop_constraint("one_label_group_per_chapter", "label_datas", type_="unique")
    op.drop_constraint("label_group_contributors_pkey", "label_group_contributors", type_="primary")

    # --- 3. drop PK on label_groups ---

    op.drop_constraint("label_groups_pkey", "label_groups", type_="primary")

    # --- 4. add new UUID columns ---

    op.add_column("label_groups", sa.Column("label_group_uuid", sa.UUID(), nullable=True))
    op.add_column("label_datas", sa.Column("label_group_uuid", sa.UUID(), nullable=True))
    op.add_column("label_group_contributors", sa.Column("label_group_uuid", sa.UUID(), nullable=True))

    # --- 5. populate UUIDs ---

    op.execute("UPDATE label_groups SET label_group_uuid = gen_random_uuid()")

    op.execute("""
        UPDATE label_datas
        SET label_group_uuid = lg.label_group_uuid
        FROM label_groups lg
        WHERE label_datas.label_group_id = lg.label_group_id
    """)

    op.execute("""
        UPDATE label_group_contributors
        SET label_group_uuid = lg.label_group_uuid
        FROM label_groups lg
        WHERE label_group_contributors.label_group_id = lg.label_group_id
    """)

    # --- 6. drop old int columns, rename new columns ---

    op.drop_column("label_datas", "label_group_id")
    op.drop_column("label_group_contributors", "label_group_id")
    op.drop_column("label_groups", "label_group_id")

    op.alter_column("label_groups", "label_group_uuid", new_column_name="label_group_id", nullable=False)
    op.alter_column("label_datas", "label_group_uuid", new_column_name="label_group_id", nullable=False)
    op.alter_column("label_group_contributors", "label_group_uuid", new_column_name="label_group_id", nullable=False)

    # --- 7. recreate PK, FK, and unique constraints ---

    op.create_primary_key("label_groups_pkey", "label_groups", ["label_group_id"])

    op.create_primary_key("label_group_contributors_pkey", "label_group_contributors", ["label_group_id", "user_id"])

    op.create_unique_constraint("one_label_group_per_chapter", "label_datas", ["label_group_id", "revision_text_id"])

    op.create_foreign_key(
        "fk_label_datas_label_group_id_label_groups",
        "label_datas",
        "label_groups",
        ["label_group_id"],
        ["label_group_id"],
    )
    op.create_foreign_key(
        "label_group_contributors_label_group_id_fkey",
        "label_group_contributors",
        "label_groups",
        ["label_group_id"],
        ["label_group_id"],
    )


def downgrade():
    op.drop_constraint("fk_label_datas_label_group_id_label_groups", "label_datas", type_="foreignkey")
    op.drop_constraint("label_group_contributors_label_group_id_fkey", "label_group_contributors", type_="foreignkey")
    op.drop_constraint("one_label_group_per_chapter", "label_datas", type_="unique")
    op.drop_constraint("label_group_contributors_pkey", "label_group_contributors", type_="primary")
    op.drop_constraint("label_groups_pkey", "label_groups", type_="primary")

    op.add_column("label_groups", sa.Column("label_group_id_int", sa.INTEGER(), autoincrement=True, nullable=True))
    op.add_column("label_datas", sa.Column("label_group_id_int", sa.INTEGER(), nullable=True))
    op.add_column("label_group_contributors", sa.Column("label_group_id_int", sa.INTEGER(), nullable=True))

    op.execute("CREATE SEQUENCE label_groups_label_group_id_seq_downgrade")
    op.execute("UPDATE label_groups SET label_group_id_int = nextval('label_groups_label_group_id_seq_downgrade')")

    op.execute("""
        UPDATE label_datas
        SET label_group_id_int = lg.label_group_id_int
        FROM label_groups lg
        WHERE label_datas.label_group_id = lg.label_group_id
    """)

    op.execute("""
        UPDATE label_group_contributors
        SET label_group_id_int = lg.label_group_id_int
        FROM label_groups lg
        WHERE label_group_contributors.label_group_id = lg.label_group_id
    """)

    op.drop_column("label_datas", "label_group_id")
    op.drop_column("label_group_contributors", "label_group_id")
    op.drop_column("label_groups", "label_group_id")

    op.alter_column("label_groups", "label_group_id_int", new_column_name="label_group_id", nullable=False)
    op.alter_column("label_datas", "label_group_id_int", new_column_name="label_group_id", nullable=False)
    op.alter_column("label_group_contributors", "label_group_id_int", new_column_name="label_group_id", nullable=False)

    op.execute("ALTER SEQUENCE label_groups_label_group_id_seq_downgrade OWNED BY label_groups.label_group_id")
    op.execute(
        "ALTER TABLE label_groups ALTER COLUMN label_group_id SET DEFAULT nextval('label_groups_label_group_id_seq_downgrade')"
    )

    op.create_primary_key("label_groups_pkey", "label_groups", ["label_group_id"])
    op.create_primary_key("label_group_contributors_pkey", "label_group_contributors", ["label_group_id", "user_id"])
    op.create_unique_constraint("one_label_group_per_chapter", "label_datas", ["label_group_id", "revision_text_id"])
    op.create_foreign_key(
        "fk_label_datas_label_group_id_label_groups",
        "label_datas",
        "label_groups",
        ["label_group_id"],
        ["label_group_id"],
    )
    op.create_foreign_key(
        "label_group_contributors_label_group_id_fkey",
        "label_group_contributors",
        "label_groups",
        ["label_group_id"],
        ["label_group_id"],
    )
