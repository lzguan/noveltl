"""migrate user id to uuid

Revision ID: 249e19cd905e
Revises: f1c373093ce9
Create Date: 2026-03-22 03:01:49.712458+00:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "249e19cd905e"
down_revision = "f1c373093ce9"
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. drop FK constraints referencing users.user_id ---

    op.drop_constraint("novel_contributors_user_id_fkey", "novel_contributors", type_="foreignkey")
    op.drop_constraint("label_group_contributors_user_id_fkey", "label_group_contributors", type_="foreignkey")

    # --- 2. drop composite PKs on contributor tables (they include user_id) ---

    op.drop_constraint("novel_contributors_pkey", "novel_contributors", type_="primary")
    op.drop_constraint("label_group_contributors_pkey", "label_group_contributors", type_="primary")

    # --- 3. drop PK on users ---

    op.drop_constraint("users_pkey", "users", type_="primary")

    # --- 4. add new UUID columns ---

    op.add_column("users", sa.Column("user_uuid", sa.UUID(), nullable=True))
    op.add_column("novel_contributors", sa.Column("user_uuid", sa.UUID(), nullable=True))
    op.add_column("label_group_contributors", sa.Column("user_uuid", sa.UUID(), nullable=True))

    # --- 5. populate UUIDs ---

    op.execute("UPDATE users SET user_uuid = gen_random_uuid()")

    op.execute("""
        UPDATE novel_contributors
        SET user_uuid = u.user_uuid
        FROM users u
        WHERE novel_contributors.user_id = u.user_id
    """)

    op.execute("""
        UPDATE label_group_contributors
        SET user_uuid = u.user_uuid
        FROM users u
        WHERE label_group_contributors.user_id = u.user_id
    """)

    # --- 6. drop old int columns, rename new columns ---

    op.drop_column("novel_contributors", "user_id")
    op.drop_column("label_group_contributors", "user_id")
    op.drop_column("users", "user_id")

    op.alter_column("users", "user_uuid", new_column_name="user_id", nullable=False)
    op.alter_column("novel_contributors", "user_uuid", new_column_name="user_id", nullable=False)
    op.alter_column("label_group_contributors", "user_uuid", new_column_name="user_id", nullable=False)

    # --- 7. recreate PK and FK constraints ---

    op.create_primary_key("users_pkey", "users", ["user_id"])
    op.create_primary_key("novel_contributors_pkey", "novel_contributors", ["novel_id", "user_id"])
    op.create_primary_key("label_group_contributors_pkey", "label_group_contributors", ["label_group_id", "user_id"])

    op.create_foreign_key("novel_contributors_user_id_fkey", "novel_contributors", "users", ["user_id"], ["user_id"])
    op.create_foreign_key(
        "label_group_contributors_user_id_fkey", "label_group_contributors", "users", ["user_id"], ["user_id"]
    )


def downgrade():
    # --- 1. drop FK and PK constraints ---

    op.drop_constraint("novel_contributors_user_id_fkey", "novel_contributors", type_="foreignkey")
    op.drop_constraint("label_group_contributors_user_id_fkey", "label_group_contributors", type_="foreignkey")
    op.drop_constraint("novel_contributors_pkey", "novel_contributors", type_="primary")
    op.drop_constraint("label_group_contributors_pkey", "label_group_contributors", type_="primary")
    op.drop_constraint("users_pkey", "users", type_="primary")

    # --- 2. add old int columns back ---

    op.add_column("users", sa.Column("user_id_int", sa.INTEGER(), autoincrement=True, nullable=True))
    op.add_column("novel_contributors", sa.Column("user_id_int", sa.INTEGER(), nullable=True))
    op.add_column("label_group_contributors", sa.Column("user_id_int", sa.INTEGER(), nullable=True))

    # --- 3. populate with sequential IDs and copy mapping ---

    op.execute("CREATE SEQUENCE users_user_id_seq")
    op.execute("UPDATE users SET user_id_int = nextval('users_user_id_seq')")

    op.execute("""
        UPDATE novel_contributors
        SET user_id_int = u.user_id_int
        FROM users u
        WHERE novel_contributors.user_id = u.user_id
    """)

    op.execute("""
        UPDATE label_group_contributors
        SET user_id_int = u.user_id_int
        FROM users u
        WHERE label_group_contributors.user_id = u.user_id
    """)

    # --- 4. drop UUID columns, rename int columns ---

    op.drop_column("novel_contributors", "user_id")
    op.drop_column("label_group_contributors", "user_id")
    op.drop_column("users", "user_id")

    op.alter_column("users", "user_id_int", new_column_name="user_id", nullable=False)
    op.alter_column("novel_contributors", "user_id_int", new_column_name="user_id", nullable=False)
    op.alter_column("label_group_contributors", "user_id_int", new_column_name="user_id", nullable=False)

    # --- 5. recreate PK and FK constraints ---

    op.execute("ALTER SEQUENCE users_user_id_seq OWNED BY users.user_id")
    op.execute("ALTER TABLE users ALTER COLUMN user_id SET DEFAULT nextval('users_user_id_seq')")

    op.create_primary_key("users_pkey", "users", ["user_id"])
    op.create_primary_key("novel_contributors_pkey", "novel_contributors", ["novel_id", "user_id"])
    op.create_primary_key("label_group_contributors_pkey", "label_group_contributors", ["label_group_id", "user_id"])

    op.create_foreign_key("novel_contributors_user_id_fkey", "novel_contributors", "users", ["user_id"], ["user_id"])
    op.create_foreign_key(
        "label_group_contributors_user_id_fkey", "label_group_contributors", "users", ["user_id"], ["user_id"]
    )
