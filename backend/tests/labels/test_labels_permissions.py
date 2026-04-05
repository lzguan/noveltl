"""
Tests for label permission functions.

Note: These tests are AI generated and may not cover all edge cases or be fully comprehensive. It is recommended to review and modify the tests as needed to ensure they align with the specific requirements and constraints of your application.
"""
import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

pytestmark = pytest.mark.dependency(
    depends=["gate::fixture_validation", "gate::novels::permissions"],
    scope="session",
)

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

    @pytest.mark.dependency(name="labels::permissions::owner_can_select_own_group", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::editor_can_select_group", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::viewer_can_select_group", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::viewer_cannot_select_with_only_editors", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::editor_can_select_with_only_editors", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::non_contributor_cannot_select_group", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::admin_can_select_any_group", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::cannot_select_group_on_private_novel", scope="session")
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

    @pytest.mark.dependency(
        name="gate::labels::permissions::label_group_select",
        depends=[
            "labels::permissions::owner_can_select_own_group",
            "labels::permissions::editor_can_select_group",
            "labels::permissions::viewer_can_select_group",
            "labels::permissions::viewer_cannot_select_with_only_editors",
            "labels::permissions::editor_can_select_with_only_editors",
            "labels::permissions::non_contributor_cannot_select_group",
            "labels::permissions::admin_can_select_any_group",
            "labels::permissions::cannot_select_group_on_private_novel",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestLabelGroupUpdate:
    """Tests for label_group_mod_access_update."""

    @pytest.mark.dependency(name="labels::permissions::owner_can_update", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::editor_can_update", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::viewer_cannot_update", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::non_contributor_cannot_update", scope="session")
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

    @pytest.mark.dependency(
        name="gate::labels::permissions::label_group_update",
        depends=[
            "labels::permissions::owner_can_update",
            "labels::permissions::editor_can_update",
            "labels::permissions::viewer_cannot_update",
            "labels::permissions::non_contributor_cannot_update",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestLabelDataSelect:
    """Tests for label_data_mod_access_select."""

    @pytest.mark.dependency(name="labels::permissions::owner_can_select_label_data", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::editor_can_select_label_data", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::viewer_can_select_label_data", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::non_contributor_cannot_select_label_data", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::cannot_select_label_data_on_private_novel", scope="session")
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

    @pytest.mark.dependency(
        name="gate::labels::permissions::label_data_select",
        depends=[
            "labels::permissions::owner_can_select_label_data",
            "labels::permissions::editor_can_select_label_data",
            "labels::permissions::viewer_can_select_label_data",
            "labels::permissions::non_contributor_cannot_select_label_data",
            "labels::permissions::cannot_select_label_data_on_private_novel",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestLabelDelete:
    """Tests for label_mod_access_delete."""

    @pytest.mark.dependency(name="labels::permissions::owner_can_delete_labels", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::editor_can_delete_labels", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::viewer_cannot_delete_labels", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::non_contributor_cannot_delete_labels", scope="session")
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

    @pytest.mark.dependency(name="labels::permissions::admin_can_delete_any_labels", scope="session")
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

    @pytest.mark.dependency(
        name="gate::labels::permissions::label_delete",
        depends=[
            "labels::permissions::owner_can_delete_labels",
            "labels::permissions::editor_can_delete_labels",
            "labels::permissions::viewer_cannot_delete_labels",
            "labels::permissions::non_contributor_cannot_delete_labels",
            "labels::permissions::admin_can_delete_any_labels",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::labels::permissions",
    depends=[
        "gate::labels::permissions::label_group_select",
        "gate::labels::permissions::label_group_update",
        "gate::labels::permissions::label_data_select",
        "gate::labels::permissions::label_delete",
    ],
    scope="session",
)
def test_gate():
    """All labels permissions tests must pass before downstream layers run."""
    pass
