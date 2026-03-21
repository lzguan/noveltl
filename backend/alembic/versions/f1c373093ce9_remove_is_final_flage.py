"""remove is_final flag, add revision_texts table

Revision ID: f1c373093ce9
Revises: 3d153d0ed511
Create Date: 2026-03-21 05:44:59.615894+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1c373093ce9'
down_revision = '3d153d0ed511'
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. drop stale FK and unique constraints ---

    # auto_labels
    op.drop_constraint('uq_model_name_params', 'auto_labels', type_='unique')
    op.drop_constraint('fk_auto_labels_revision_id_revisions', 'auto_labels', type_='foreignkey')

    # label_datas
    op.drop_constraint('one_label_group_per_chapter', 'label_datas', type_='unique')
    op.drop_constraint('fk_label_datas_revision_id_revisions', 'label_datas', type_='foreignkey')

    # --- 2. create revision_texts table ---

    op.create_table('revision_texts',
        sa.Column('revision_text_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('revision_text_content', sa.Text(), nullable=False),
        sa.Column('revision_text_version', sa.Integer(), nullable=False),
        sa.Column('revision_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['revision_id'], ['revisions.revision_id'], name='fk_revision_texts_revision_id_revisions'),
        sa.PrimaryKeyConstraint('revision_text_id'),
        sa.UniqueConstraint('revision_id', 'revision_text_version', name='uq_revision_text_version_per_revision')
    )

    # --- 3. add new nullable FK columns ---

    op.add_column('auto_labels', sa.Column('revision_text_id', sa.UUID(), nullable=True))
    op.add_column('label_datas', sa.Column('revision_text_id', sa.UUID(), nullable=True))

    # --- 4. copy revision text into revision_texts (version 1 for each) ---

    op.execute("""
        INSERT INTO revision_texts (revision_text_content, revision_text_version, revision_id, created_at, updated_at)
        SELECT revision_text, 1, revision_id, now(), now()
        FROM revisions
    """)

    # --- 5. populate revision_text_id on label_datas and auto_labels ---

    op.execute("""
        UPDATE label_datas
        SET revision_text_id = rt.revision_text_id
        FROM revision_texts rt
        WHERE rt.revision_id = label_datas.revision_id
    """)

    op.execute("""
        UPDATE auto_labels
        SET revision_text_id = rt.revision_text_id
        FROM revision_texts rt
        WHERE rt.revision_id = auto_labels.revision_id
    """)

    # --- 6. make new columns non-nullable, drop old columns, recreate constraints ---

    op.alter_column('auto_labels', 'revision_text_id', nullable=False)
    op.alter_column('label_datas', 'revision_text_id', nullable=False)

    op.drop_column('auto_labels', 'revision_id')
    op.drop_column('label_datas', 'revision_id')

    op.drop_column('revisions', 'revision_text')
    op.drop_column('revisions', 'revision_is_final')

    # recreate constraints: auto_labels
    op.create_unique_constraint('uq_model_name_params', 'auto_labels', ['revision_text_id', 'auto_label_model_name', 'auto_label_model_params'])
    op.create_foreign_key('fk_auto_labels_revision_text_id_revision_texts', 'auto_labels', 'revision_texts', ['revision_text_id'], ['revision_text_id'])

    # recreate constraints: label_datas
    op.create_unique_constraint('one_label_group_per_chapter', 'label_datas', ['label_group_id', 'revision_text_id'])
    op.create_foreign_key('fk_label_datas_revision_text_id_revision_texts', 'label_datas', 'revision_texts', ['revision_text_id'], ['revision_text_id'])


def downgrade():
    # --- drop new constraints ---

    op.drop_constraint('uq_model_name_params', 'auto_labels', type_='unique')
    op.drop_constraint('fk_auto_labels_revision_text_id_revision_texts', 'auto_labels', type_='foreignkey')
    op.drop_constraint('one_label_group_per_chapter', 'label_datas', type_='unique')
    op.drop_constraint('fk_label_datas_revision_text_id_revision_texts', 'label_datas', type_='foreignkey')

    # --- restore revision_text and revision_is_final on revisions ---

    op.add_column('revisions', sa.Column('revision_is_final', sa.BOOLEAN(), nullable=True))
    op.add_column('revisions', sa.Column('revision_text', sa.TEXT(), nullable=True))

    # backfill from revision_texts (take version 1)
    op.execute("""
        UPDATE revisions
        SET revision_text = rt.revision_text_content,
            revision_is_final = false
        FROM revision_texts rt
        WHERE rt.revision_id = revisions.revision_id
          AND rt.revision_text_version = 1
    """)

    op.alter_column('revisions', 'revision_is_final', nullable=False)
    op.alter_column('revisions', 'revision_text', nullable=False)

    # --- restore revision_id columns on label_datas and auto_labels ---

    op.add_column('label_datas', sa.Column('revision_id', sa.INTEGER(), nullable=True))
    op.add_column('auto_labels', sa.Column('revision_id', sa.INTEGER(), nullable=True))

    # backfill revision_id from revision_texts
    op.execute("""
        UPDATE label_datas
        SET revision_id = rt.revision_id
        FROM revision_texts rt
        WHERE rt.revision_text_id = label_datas.revision_text_id
    """)

    op.execute("""
        UPDATE auto_labels
        SET revision_id = rt.revision_id
        FROM revision_texts rt
        WHERE rt.revision_text_id = auto_labels.revision_text_id
    """)

    op.alter_column('label_datas', 'revision_id', nullable=False)
    op.alter_column('auto_labels', 'revision_id', nullable=False)

    # --- drop new columns and table ---

    op.drop_column('label_datas', 'revision_text_id')
    op.drop_column('auto_labels', 'revision_text_id')
    op.drop_table('revision_texts')

    # --- recreate old constraints ---

    op.create_unique_constraint('one_label_group_per_chapter', 'label_datas', ['label_group_id', 'revision_id'])
    op.create_foreign_key('fk_label_datas_revision_id_revisions', 'label_datas', 'revisions', ['revision_id'], ['revision_id'])
    op.create_unique_constraint('uq_model_name_params', 'auto_labels', ['revision_id', 'auto_label_model_name', 'auto_label_model_params'])
    op.create_foreign_key('fk_auto_labels_revision_id_revisions', 'auto_labels', 'revisions', ['revision_id'], ['revision_id'])
