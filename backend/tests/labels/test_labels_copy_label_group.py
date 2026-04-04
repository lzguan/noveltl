"""
Tests for copy_label_group function.

Note: This test is AI generated and may not cover all edge cases or be fully comprehensive. It is recommended to review and modify the tests as needed to ensure they align with the specific requirements and constraints of your application.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.filters.utils import copy_label_group
from src.labels import models as label_models
from src.labels.constants import LabelRole
from src.labels.exceptions import LabelGroupNotFoundException


class TestCopyLabelGroup:
    """Tests for the copy_label_group function."""

    def test_owner_can_copy_label_group(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_label_group_owner_only: label_models.LabelGroup,
        lp_label_data_owner_only: label_models.LabelData,
        lp_labels_owner_only: list[label_models.Label],
    ):
        new_group = copy_label_group(
            test_db,
            lp_user_1,
            lp_label_group_owner_only.label_group_id,
            "Copied Group"
        )

        assert new_group.label_group_name == "Copied Group"
        assert new_group.novel_id == lp_label_group_owner_only.novel_id
        assert new_group.label_group_id != lp_label_group_owner_only.label_group_id

    def test_editor_can_copy_label_group(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_group_with_editor: label_models.LabelGroup,
        lp_label_data_with_editor: label_models.LabelData,
        lp_labels_with_editor: list[label_models.Label],
    ):
        new_group = copy_label_group(
            test_db,
            lp_user_2,
            lp_label_group_with_editor.label_group_id,
            "Editor Copy"
        )
        assert new_group is not None
        assert new_group.label_group_name == "Editor Copy"

    def test_viewer_cannot_copy_label_group(
        self,
        test_db: Session,
        lp_user_2: User,
        lp_label_group_with_viewer: label_models.LabelGroup,
        lp_label_data_with_viewer: label_models.LabelData,
    ):
        with pytest.raises(LabelGroupNotFoundException):
            copy_label_group(
                test_db,
                lp_user_2,
                lp_label_group_with_viewer.label_group_id,
                "Should Fail"
            )

    def test_non_contributor_cannot_copy(
        self,
        test_db: Session,
        lp_user_3: User,
        lp_label_group_owner_only: label_models.LabelGroup,
    ):
        with pytest.raises(LabelGroupNotFoundException):
            copy_label_group(
                test_db,
                lp_user_3,
                lp_label_group_owner_only.label_group_id,
                "Should Fail"
            )

    def test_copy_preserves_contributors(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_user_2: User,
        lp_label_group_with_editor: label_models.LabelGroup,
        lp_label_data_with_editor: label_models.LabelData,
    ):
        new_group = copy_label_group(
            test_db,
            lp_user_1,
            lp_label_group_with_editor.label_group_id,
            "With Contributors",
            keep_contributors=True
        )

        contributors = test_db.execute(
            select(label_models.LabelContributor).where(
                label_models.LabelContributor.label_group_id == new_group.label_group_id
            )
        ).scalars().all()

        assert len(contributors) == 2
        user_ids = {c.user_id for c in contributors}
        assert lp_user_1.user_id in user_ids
        assert lp_user_2.user_id in user_ids

    def test_copy_without_contributors_sets_current_user_as_owner(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_user_2: User,
        lp_label_group_with_editor: label_models.LabelGroup,
        lp_label_data_with_editor: label_models.LabelData,
    ):
        new_group = copy_label_group(
            test_db,
            lp_user_1,
            lp_label_group_with_editor.label_group_id,
            "New Owner Only",
            keep_contributors=False
        )

        contributors = test_db.execute(
            select(label_models.LabelContributor).where(
                label_models.LabelContributor.label_group_id == new_group.label_group_id
            )
        ).scalars().all()

        assert len(contributors) == 1
        assert contributors[0].user_id == lp_user_1.user_id
        assert contributors[0].label_contributor_role == LabelRole.OWNER

    def test_copy_includes_label_data(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_label_group_owner_only: label_models.LabelGroup,
        lp_label_data_owner_only: label_models.LabelData,
        lp_labels_owner_only: list[label_models.Label],
    ):
        new_group = copy_label_group(
            test_db,
            lp_user_1,
            lp_label_group_owner_only.label_group_id,
            "With Data"
        )

        label_datas = test_db.execute(
            select(label_models.LabelData).where(
                label_models.LabelData.label_group_id == new_group.label_group_id
            )
        ).scalars().all()

        assert len(label_datas) == 1
        assert label_datas[0].chapter_content_id == lp_label_data_owner_only.chapter_content_id

    def test_copy_includes_labels(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_label_group_owner_only: label_models.LabelGroup,
        lp_label_data_owner_only: label_models.LabelData,
        lp_labels_owner_only: list[label_models.Label],
    ):
        new_group = copy_label_group(
            test_db,
            lp_user_1,
            lp_label_group_owner_only.label_group_id,
            "With Labels"
        )

        new_label_data = test_db.execute(
            select(label_models.LabelData).where(
                label_models.LabelData.label_group_id == new_group.label_group_id
            )
        ).scalar_one()

        new_labels = test_db.execute(
            select(label_models.Label).where(
                label_models.Label.label_data_id == new_label_data.label_data_id
            ).order_by(label_models.Label.label_start)
        ).scalars().all()

        assert len(new_labels) == len(lp_labels_owner_only)
        for new_label, orig_label in zip(new_labels, sorted(lp_labels_owner_only, key=lambda x: x.label_start), strict=False):
            assert new_label.label_word == orig_label.label_word
            assert new_label.label_start == orig_label.label_start
            assert new_label.label_end == orig_label.label_end
            assert new_label.label_entity_group == orig_label.label_entity_group

    def test_copy_does_not_affect_original(
        self,
        test_db: Session,
        lp_user_1: User,
        lp_label_group_owner_only: label_models.LabelGroup,
        lp_label_data_owner_only: label_models.LabelData,
        lp_labels_owner_only: list[label_models.Label],
    ):
        original_label_count = len(lp_labels_owner_only)

        copy_label_group(
            test_db,
            lp_user_1,
            lp_label_group_owner_only.label_group_id,
            "Copy"
        )

        # Verify original still intact
        original_labels = test_db.execute(
            select(label_models.Label).where(
                label_models.Label.label_data_id == lp_label_data_owner_only.label_data_id
            )
        ).scalars().all()

        assert len(original_labels) == original_label_count
