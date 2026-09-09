"""add glossary term kind

Revision ID: 61d8d246e12a
Revises: df9890b9fdd4
Create Date: 2026-08-29 01:00:00+00:00

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "61d8d246e12a"
down_revision = "df9890b9fdd4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "glossaries",
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
    )


def downgrade():
    op.drop_column("glossaries", "term_kind")
