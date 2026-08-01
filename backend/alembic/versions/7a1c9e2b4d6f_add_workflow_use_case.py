"""add workflow use case

Revision ID: 7a1c9e2b4d6f
Revises: fa743ea4464a
Create Date: 2026-08-01 00:00:00.000000+00:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "7a1c9e2b4d6f"
down_revision = "fa743ea4464a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workflows",
        sa.Column(
            "use_case",
            sa.Enum(
                "advanced",
                "glossary",
                name="workflowusecase",
                native_enum=False,
                length=10,
            ),
            server_default="advanced",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("workflows", "use_case")
