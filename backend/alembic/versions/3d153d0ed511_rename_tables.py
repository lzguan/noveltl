"""rename tables

Revision ID: 3d153d0ed511
Revises: 06741dac5042
Create Date: 2026-03-21 04:58:44.986770+00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3d153d0ed511'
down_revision = '06741dac5042'
branch_labels = None
depends_on = None


def upgrade():
    # --- drop all constraints referencing old names ---

    # auto_labels
    op.drop_constraint('uq_model_name_params', 'auto_labels', type_='unique')
    op.drop_constraint('fk_auto_labels_raw_chapter_revision_id_raw_chapter_revisions', 'auto_labels', type_='foreignkey')

    # label_datas
    op.drop_constraint('one_label_group_per_chapter', 'label_datas', type_='unique')
    op.drop_constraint('fk_label_datas_raw_chapter_revision_id_raw_chapter_revisions', 'label_datas', type_='foreignkey')

    # raw_chapter_revisions
    op.drop_constraint('fk_raw_chapter_revisions_raw_chapter_id_raw_chapters', 'raw_chapter_revisions', type_='foreignkey')
    op.drop_constraint('primary_must_be_public_check', 'raw_chapter_revisions', type_='check')
    op.drop_index('ix_one_primary_revision_per_chapter', table_name='raw_chapter_revisions')
    op.drop_constraint('raw_chapter_revisions_pkey', 'raw_chapter_revisions', type_='primary')

    # raw_chapters
    op.drop_constraint('raw_chapter_per_novel', 'raw_chapters', type_='unique')
    op.drop_constraint('fk_raw_chapters_novel_id_novels', 'raw_chapters', type_='foreignkey')
    op.drop_constraint('raw_chapters_pkey', 'raw_chapters', type_='primary')

    # --- rename tables ---

    op.rename_table('raw_chapters', 'chapters')
    op.rename_table('raw_chapter_revisions', 'revisions')

    # --- rename columns: chapters ---

    op.alter_column('chapters', 'raw_chapter_id', new_column_name='chapter_id')
    op.alter_column('chapters', 'raw_chapter_num', new_column_name='chapter_num')

    # --- rename columns: revisions ---

    op.alter_column('revisions', 'raw_chapter_revision_id', new_column_name='revision_id')
    op.alter_column('revisions', 'raw_chapter_revision_text', new_column_name='revision_text')
    op.alter_column('revisions', 'raw_chapter_revision_title', new_column_name='revision_title')
    op.alter_column('revisions', 'raw_chapter_revision_is_primary', new_column_name='revision_is_primary')
    op.alter_column('revisions', 'raw_chapter_revision_is_public', new_column_name='revision_is_public')
    op.alter_column('revisions', 'raw_chapter_revision_is_final', new_column_name='revision_is_final')
    op.alter_column('revisions', 'raw_chapter_id', new_column_name='chapter_id')

    # --- rename FK columns on other tables ---

    op.alter_column('label_datas', 'raw_chapter_revision_id', new_column_name='revision_id')
    op.alter_column('auto_labels', 'raw_chapter_revision_id', new_column_name='revision_id')

    # --- rename sequences ---

    op.execute('ALTER SEQUENCE raw_chapters_raw_chapter_id_seq RENAME TO chapters_chapter_id_seq')
    op.execute('ALTER SEQUENCE raw_chapter_revisions_raw_chapter_revision_id_seq RENAME TO revisions_revision_id_seq')

    # --- rename NOT NULL constraints (no Alembic API for these) ---

    # chapters
    op.execute('ALTER TABLE chapters RENAME CONSTRAINT raw_chapters_raw_chapter_id_not_null TO chapters_chapter_id_not_null')
    op.execute('ALTER TABLE chapters RENAME CONSTRAINT raw_chapters_raw_chapter_num_not_null TO chapters_chapter_num_not_null')
    op.execute('ALTER TABLE chapters RENAME CONSTRAINT raw_chapters_novel_id_not_null TO chapters_novel_id_not_null')
    op.execute('ALTER TABLE chapters RENAME CONSTRAINT raw_chapters_created_at_not_null TO chapters_created_at_not_null')
    op.execute('ALTER TABLE chapters RENAME CONSTRAINT raw_chapters_updated_at_not_null TO chapters_updated_at_not_null')

    # revisions
    op.execute('ALTER TABLE revisions RENAME CONSTRAINT raw_chapter_revisions_raw_chapter_revision_id_not_null TO revisions_revision_id_not_null')
    op.execute('ALTER TABLE revisions RENAME CONSTRAINT raw_chapter_revisions_raw_chapter_revision_text_not_null TO revisions_revision_text_not_null')
    op.execute('ALTER TABLE revisions RENAME CONSTRAINT raw_chapter_revisions_raw_chapter_revision_title_not_null TO revisions_revision_title_not_null')
    op.execute('ALTER TABLE revisions RENAME CONSTRAINT raw_chapter_revisions_raw_chapter_revision_is_primary_not_null TO revisions_revision_is_primary_not_null')
    op.execute('ALTER TABLE revisions RENAME CONSTRAINT raw_chapter_revisions_raw_chapter_revision_is_public_not_null TO revisions_revision_is_public_not_null')
    op.execute('ALTER TABLE revisions RENAME CONSTRAINT raw_chapter_revisions_raw_chapter_revision_is_final_not_null TO revisions_revision_is_final_not_null')
    op.execute('ALTER TABLE revisions RENAME CONSTRAINT raw_chapter_revisions_raw_chapter_id_not_null TO revisions_chapter_id_not_null')
    op.execute('ALTER TABLE revisions RENAME CONSTRAINT raw_chapter_revisions_created_at_not_null TO revisions_created_at_not_null')
    op.execute('ALTER TABLE revisions RENAME CONSTRAINT raw_chapter_revisions_updated_at_not_null TO revisions_updated_at_not_null')

    # label_datas
    op.execute('ALTER TABLE label_datas RENAME CONSTRAINT label_datas_raw_chapter_revision_id_not_null TO label_datas_revision_id_not_null')

    # auto_labels
    op.execute('ALTER TABLE auto_labels RENAME CONSTRAINT auto_labels_raw_chapter_revision_id_not_null TO auto_labels_revision_id_not_null')

    # --- recreate constraints: chapters ---

    op.create_primary_key('chapters_pkey', 'chapters', ['chapter_id'])
    op.create_unique_constraint('chapter_per_novel', 'chapters', ['chapter_num', 'novel_id'])
    op.create_foreign_key('fk_chapters_novel_id_novels', 'chapters', 'novels', ['novel_id'], ['novel_id'])

    # --- recreate constraints: revisions ---

    op.create_primary_key('revisions_pkey', 'revisions', ['revision_id'])
    op.create_foreign_key('fk_revisions_chapter_id_chapters', 'revisions', 'chapters', ['chapter_id'], ['chapter_id'])
    op.create_check_constraint('primary_must_be_public_check', 'revisions', 'revision_is_public OR NOT revision_is_primary')
    op.create_index('ix_one_primary_revision_per_chapter', 'revisions', ['chapter_id'], unique=True, postgresql_where=sa.text('revision_is_primary IS true'))

    # --- recreate constraints: label_datas ---

    op.create_unique_constraint('one_label_group_per_chapter', 'label_datas', ['label_group_id', 'revision_id'])
    op.create_foreign_key('fk_label_datas_revision_id_revisions', 'label_datas', 'revisions', ['revision_id'], ['revision_id'])

    # --- recreate constraints: auto_labels ---

    op.create_unique_constraint('uq_model_name_params', 'auto_labels', ['revision_id', 'auto_label_model_name', 'auto_label_model_params'])
    op.create_foreign_key('fk_auto_labels_revision_id_revisions', 'auto_labels', 'revisions', ['revision_id'], ['revision_id'])


def downgrade():
    # --- drop constraints with new names ---

    # auto_labels
    op.drop_constraint('uq_model_name_params', 'auto_labels', type_='unique')
    op.drop_constraint('fk_auto_labels_revision_id_revisions', 'auto_labels', type_='foreignkey')

    # label_datas
    op.drop_constraint('one_label_group_per_chapter', 'label_datas', type_='unique')
    op.drop_constraint('fk_label_datas_revision_id_revisions', 'label_datas', type_='foreignkey')

    # revisions
    op.drop_constraint('fk_revisions_chapter_id_chapters', 'revisions', type_='foreignkey')
    op.drop_constraint('primary_must_be_public_check', 'revisions', type_='check')
    op.drop_index('ix_one_primary_revision_per_chapter', table_name='revisions')
    op.drop_constraint('revisions_pkey', 'revisions', type_='primary')

    # chapters
    op.drop_constraint('chapter_per_novel', 'chapters', type_='unique')
    op.drop_constraint('fk_chapters_novel_id_novels', 'chapters', type_='foreignkey')
    op.drop_constraint('chapters_pkey', 'chapters', type_='primary')

    # --- rename FK columns on other tables back ---

    op.alter_column('label_datas', 'revision_id', new_column_name='raw_chapter_revision_id')
    op.alter_column('auto_labels', 'revision_id', new_column_name='raw_chapter_revision_id')

    # --- rename columns: revisions back ---

    op.alter_column('revisions', 'revision_id', new_column_name='raw_chapter_revision_id')
    op.alter_column('revisions', 'revision_text', new_column_name='raw_chapter_revision_text')
    op.alter_column('revisions', 'revision_title', new_column_name='raw_chapter_revision_title')
    op.alter_column('revisions', 'revision_is_primary', new_column_name='raw_chapter_revision_is_primary')
    op.alter_column('revisions', 'revision_is_public', new_column_name='raw_chapter_revision_is_public')
    op.alter_column('revisions', 'revision_is_final', new_column_name='raw_chapter_revision_is_final')
    op.alter_column('revisions', 'chapter_id', new_column_name='raw_chapter_id')

    # --- rename columns: chapters back ---

    op.alter_column('chapters', 'chapter_id', new_column_name='raw_chapter_id')
    op.alter_column('chapters', 'chapter_num', new_column_name='raw_chapter_num')

    # --- rename tables back ---

    op.rename_table('chapters', 'raw_chapters')
    op.rename_table('revisions', 'raw_chapter_revisions')

    # --- rename sequences back ---

    op.execute('ALTER SEQUENCE chapters_chapter_id_seq RENAME TO raw_chapters_raw_chapter_id_seq')
    op.execute('ALTER SEQUENCE revisions_revision_id_seq RENAME TO raw_chapter_revisions_raw_chapter_revision_id_seq')

    # --- rename NOT NULL constraints back ---

    # raw_chapters
    op.execute('ALTER TABLE raw_chapters RENAME CONSTRAINT chapters_chapter_id_not_null TO raw_chapters_raw_chapter_id_not_null')
    op.execute('ALTER TABLE raw_chapters RENAME CONSTRAINT chapters_chapter_num_not_null TO raw_chapters_raw_chapter_num_not_null')
    op.execute('ALTER TABLE raw_chapters RENAME CONSTRAINT chapters_novel_id_not_null TO raw_chapters_novel_id_not_null')
    op.execute('ALTER TABLE raw_chapters RENAME CONSTRAINT chapters_created_at_not_null TO raw_chapters_created_at_not_null')
    op.execute('ALTER TABLE raw_chapters RENAME CONSTRAINT chapters_updated_at_not_null TO raw_chapters_updated_at_not_null')

    # raw_chapter_revisions
    op.execute('ALTER TABLE raw_chapter_revisions RENAME CONSTRAINT revisions_revision_id_not_null TO raw_chapter_revisions_raw_chapter_revision_id_not_null')
    op.execute('ALTER TABLE raw_chapter_revisions RENAME CONSTRAINT revisions_revision_text_not_null TO raw_chapter_revisions_raw_chapter_revision_text_not_null')
    op.execute('ALTER TABLE raw_chapter_revisions RENAME CONSTRAINT revisions_revision_title_not_null TO raw_chapter_revisions_raw_chapter_revision_title_not_null')
    op.execute('ALTER TABLE raw_chapter_revisions RENAME CONSTRAINT revisions_revision_is_primary_not_null TO raw_chapter_revisions_raw_chapter_revision_is_primary_not_null')
    op.execute('ALTER TABLE raw_chapter_revisions RENAME CONSTRAINT revisions_revision_is_public_not_null TO raw_chapter_revisions_raw_chapter_revision_is_public_not_null')
    op.execute('ALTER TABLE raw_chapter_revisions RENAME CONSTRAINT revisions_revision_is_final_not_null TO raw_chapter_revisions_raw_chapter_revision_is_final_not_null')
    op.execute('ALTER TABLE raw_chapter_revisions RENAME CONSTRAINT revisions_chapter_id_not_null TO raw_chapter_revisions_raw_chapter_id_not_null')
    op.execute('ALTER TABLE raw_chapter_revisions RENAME CONSTRAINT revisions_created_at_not_null TO raw_chapter_revisions_created_at_not_null')
    op.execute('ALTER TABLE raw_chapter_revisions RENAME CONSTRAINT revisions_updated_at_not_null TO raw_chapter_revisions_updated_at_not_null')

    # label_datas
    op.execute('ALTER TABLE label_datas RENAME CONSTRAINT label_datas_revision_id_not_null TO label_datas_raw_chapter_revision_id_not_null')

    # auto_labels
    op.execute('ALTER TABLE auto_labels RENAME CONSTRAINT auto_labels_revision_id_not_null TO auto_labels_raw_chapter_revision_id_not_null')

    # --- recreate constraints: raw_chapters ---

    op.create_primary_key('raw_chapters_pkey', 'raw_chapters', ['raw_chapter_id'])
    op.create_unique_constraint('raw_chapter_per_novel', 'raw_chapters', ['raw_chapter_num', 'novel_id'])
    op.create_foreign_key('fk_raw_chapters_novel_id_novels', 'raw_chapters', 'novels', ['novel_id'], ['novel_id'])

    # --- recreate constraints: raw_chapter_revisions ---

    op.create_primary_key('raw_chapter_revisions_pkey', 'raw_chapter_revisions', ['raw_chapter_revision_id'])
    op.create_foreign_key('fk_raw_chapter_revisions_raw_chapter_id_raw_chapters', 'raw_chapter_revisions', 'raw_chapters', ['raw_chapter_id'], ['raw_chapter_id'])
    op.create_check_constraint('primary_must_be_public_check', 'raw_chapter_revisions', 'raw_chapter_revision_is_public OR NOT raw_chapter_revision_is_primary')
    op.create_index('ix_one_primary_revision_per_chapter', 'raw_chapter_revisions', ['raw_chapter_id'], unique=True, postgresql_where=sa.text('raw_chapter_revision_is_primary IS true'))

    # --- recreate constraints: label_datas ---

    op.create_unique_constraint('one_label_group_per_chapter', 'label_datas', ['label_group_id', 'raw_chapter_revision_id'])
    op.create_foreign_key('fk_label_datas_raw_chapter_revision_id_raw_chapter_revisions', 'label_datas', 'raw_chapter_revisions', ['raw_chapter_revision_id'], ['raw_chapter_revision_id'])

    # --- recreate constraints: auto_labels ---

    op.create_unique_constraint('uq_model_name_params', 'auto_labels', ['raw_chapter_revision_id', 'auto_label_model_name', 'auto_label_model_params'])
    op.create_foreign_key('fk_auto_labels_raw_chapter_revision_id_raw_chapter_revisions', 'auto_labels', 'raw_chapter_revisions', ['raw_chapter_revision_id'], ['raw_chapter_revision_id'])
