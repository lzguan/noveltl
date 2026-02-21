"""
Tests for label permission functions.

Note: These tests are AI generated and may not cover all edge cases or be fully comprehensive. It is recommended to review and modify the tests as needed to ensure they align with the specific requirements and constraints of your application.
"""
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from src.auth.models import User
from src.labels import models as label_models
from src.labels.permissions import (
    label_data_mod_access_select,
    label_group_mod_access_select,
    label_group_mod_access_update,
    label_mod_access_delete,
)


class TestLabelGroupSelect:
    """Tests for label_group_mod_access_select."""

    def test_owner_can_select_own_group(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_label_group_owner_only: label_models.LabelGroup,
    ):
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == lp_label_group_owner_only.label_group_id
        )
        q = label_group_mod_access_select(q, lp_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None
        assert result.label_group_id == lp_label_group_owner_only.label_group_id

    def test_editor_can_select_group(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_group_with_editor: label_models.LabelGroup,
    ):
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == lp_label_group_with_editor.label_group_id
        )
        q = label_group_mod_access_select(q, lp_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_can_select_group(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_group_with_viewer: label_models.LabelGroup,
    ):
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == lp_label_group_with_viewer.label_group_id
        )
        q = label_group_mod_access_select(q, lp_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_select_with_only_editors(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_group_with_viewer: label_models.LabelGroup,
    ):
        """Viewer should not be able to select when only_editors=True."""
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == lp_label_group_with_viewer.label_group_id
        )
        q = label_group_mod_access_select(q, lp_user_2, only_editors=True)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_editor_can_select_with_only_editors(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_group_with_editor: label_models.LabelGroup,
    ):
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == lp_label_group_with_editor.label_group_id
        )
        q = label_group_mod_access_select(q, lp_user_2, only_editors=True)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_non_contributor_cannot_select_group(
        self,
        test_db: Session,
        lp_user_3: User,
        lp_label_group_owner_only: label_models.LabelGroup,
    ):
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == lp_label_group_owner_only.label_group_id
        )
        q = label_group_mod_access_select(q, lp_user_3)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_admin_can_select_any_group(
        self,
        test_db: Session,
        lp_admin: User,
        lp_label_group_owner_only: label_models.LabelGroup,
    ):
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == lp_label_group_owner_only.label_group_id
        )
        q = label_group_mod_access_select(q, lp_admin)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_cannot_select_group_on_private_novel_without_access(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_group_private_novel: label_models.LabelGroup,
    ):
        """user_2 has no access to the private novel, so cannot see label group."""
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == lp_label_group_private_novel.label_group_id
        )
        q = label_group_mod_access_select(q, lp_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None


class TestLabelGroupUpdate:
    """Tests for label_group_mod_access_update."""

    def test_owner_can_update(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_label_group_owner_only: label_models.LabelGroup,
    ):
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == lp_label_group_owner_only.label_group_id)
            .values(label_group_name="Updated Name")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, lp_user_1)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None
        assert result.label_group_name == "Updated Name"

    def test_editor_can_update(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_group_with_editor: label_models.LabelGroup,
    ):
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == lp_label_group_with_editor.label_group_id)
            .values(label_group_name="Editor Updated")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, lp_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_update(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_group_with_viewer: label_models.LabelGroup,
    ):
        original_name = lp_label_group_with_viewer.label_group_name
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == lp_label_group_with_viewer.label_group_id)
            .values(label_group_name="Should Not Update")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, lp_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None
        # Verify it wasn't updated
        test_db.refresh(lp_label_group_with_viewer)
        assert lp_label_group_with_viewer.label_group_name == original_name

    def test_non_contributor_cannot_update(
        self,
        test_db: Session,
        lp_user_3: User,
        lp_label_group_owner_only: label_models.LabelGroup,
    ):
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == lp_label_group_owner_only.label_group_id)
            .values(label_group_name="Hacked")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, lp_user_3)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None


class TestLabelDataSelect:
    """Tests for label_data_mod_access_select."""

    def test_owner_can_select_label_data(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_label_data_owner_only: label_models.LabelData,
    ):
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == lp_label_data_owner_only.label_data_id
        )
        q = label_data_mod_access_select(q, lp_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_editor_can_select_label_data(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_data_with_editor: label_models.LabelData,
    ):
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == lp_label_data_with_editor.label_data_id
        )
        q = label_data_mod_access_select(q, lp_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_can_select_label_data(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_data_with_viewer: label_models.LabelData,
    ):
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == lp_label_data_with_viewer.label_data_id
        )
        q = label_data_mod_access_select(q, lp_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_non_contributor_cannot_select_label_data(
        self,
        test_db: Session,
        lp_user_3: User,
        lp_label_data_owner_only: label_models.LabelData,
    ):
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == lp_label_data_owner_only.label_data_id
        )
        q = label_data_mod_access_select(q, lp_user_3)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_cannot_select_label_data_on_private_novel(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_data_private_novel: label_models.LabelData,
    ):
        """user_2 cannot see label data on private novel they have no access to."""
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == lp_label_data_private_novel.label_data_id
        )
        q = label_data_mod_access_select(q, lp_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None


class TestLabelDelete:
    """Tests for label_mod_access_delete."""

    def test_owner_can_delete_labels(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_labels_owner_only: list[label_models.Label],
        lp_label_data_owner_only: label_models.LabelData,
    ):
        label_ids = [lab.label_id for lab in lp_labels_owner_only]
        stmt = delete(label_models.Label).where(
            label_models.Label.label_id.in_(label_ids)
        )
        stmt = label_mod_access_delete(stmt, lp_user_1)
        test_db.execute(stmt)
        test_db.commit()

        # Verify deleted
        remaining = test_db.execute(
            select(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        ).scalars().all()
        assert len(remaining) == 0

    def test_editor_can_delete_labels(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_labels_with_editor: list[label_models.Label],
    ):
        label_ids = [lab.label_id for lab in lp_labels_with_editor]
        stmt = delete(label_models.Label).where(
            label_models.Label.label_id.in_(label_ids)
        )
        stmt = label_mod_access_delete(stmt, lp_user_2)
        test_db.execute(stmt)
        test_db.commit()

        remaining = test_db.execute(
            select(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        ).scalars().all()
        assert len(remaining) == 0

    def test_viewer_cannot_delete_labels(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_labels_with_viewer: list[label_models.Label],
    ):
        label_ids = [lab.label_id for lab in lp_labels_with_viewer]
        stmt = delete(label_models.Label).where(
            label_models.Label.label_id.in_(label_ids)
        )
        stmt = label_mod_access_delete(stmt, lp_user_2)
        test_db.execute(stmt)
        test_db.commit()

        # Verify NOT deleted
        remaining = test_db.execute(
            select(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        ).scalars().all()
        assert len(remaining) == len(lp_labels_with_viewer)

    def test_non_contributor_cannot_delete_labels(
        self,
        test_db: Session,
        lp_user_3: User,
        lp_labels_owner_only: list[label_models.Label],
    ):
        label_ids = [lab.label_id for lab in lp_labels_owner_only]
        stmt = delete(label_models.Label).where(
            label_models.Label.label_id.in_(label_ids)
        )
        stmt = label_mod_access_delete(stmt, lp_user_3)
        test_db.execute(stmt)
        test_db.commit()

        # Verify NOT deleted
        remaining = test_db.execute(
            select(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        ).scalars().all()
        assert len(remaining) == len(lp_labels_owner_only)

    def test_admin_can_delete_any_labels(
        self,
        test_db: Session,
        lp_admin: User,
        lp_labels_owner_only: list[label_models.Label],
    ):
        label_ids = [lab.label_id for lab in lp_labels_owner_only]
        stmt = delete(label_models.Label).where(
            label_models.Label.label_id.in_(label_ids)
        )
        stmt = label_mod_access_delete(stmt, lp_admin)
        test_db.execute(stmt)
        test_db.commit()

        remaining = test_db.execute(
            select(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        ).scalars().all()
        assert len(remaining) == 0
