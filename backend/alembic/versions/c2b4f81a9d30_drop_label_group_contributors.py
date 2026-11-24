"""drop label_group_contributors table

Revision ID: c2b4f81a9d30
Revises: 4ea4c662b46f
Create Date: 2026-11-24 09:38:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c2b4f81a9d30"
down_revision: str | Sequence[str] | None = "4ea4c662b46f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("label_group_contributors")


def downgrade() -> None:
    op.create_table(
        "label_group_contributors",
        sa.Column(
            "label_contributor_role",
            sa.Enum("owner", "viewer", "editor", name="labelrole", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("label_group_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["label_group_id"], ["label_groups.label_group_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("label_group_id", "user_id"),
    )
