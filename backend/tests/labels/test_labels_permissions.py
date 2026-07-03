"""
Tests for label permission functions.

Note: These tests are AI generated and may not cover all edge cases or be fully comprehensive. It is recommended to review and modify the tests as needed to ensure they align with the specific requirements and constraints of your application.
"""

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, aliased

from src.auth.models import User
from src.labels import models as label_models
from src.labels.constants import LabelRole
from src.labels.permissions import (
    label_data_mod_access_select,
    label_group_mod_access_select,
    label_group_mod_access_update,
    label_mod_access_delete,
    label_mod_access_update,
)
from tests.fixtures.bundles import LabelFixtureBundle, ScenarioBundle
from tests.gate_logging import log_gate

pytestmark = pytest.mark.dependency(
    depends=["gate::fixture_validation", "gate::novels::permissions"],
    scope="session",
)


def _label_access_user(bundle: ScenarioBundle, user_name: str) -> User:
    return bundle.users.by_name[user_name]


def _label_access_group(bundle: ScenarioBundle, group_name: str) -> LabelFixtureBundle:
    return bundle.label_groups_by_name[group_name]


class TestLabelGroupSelect:
    """Tests for label_group_mod_access_select."""

    @pytest.mark.dependency(name="labels::permissions::owner_can_select_own_group", scope="session")
    def test_owner_can_select_own_group(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id
        )
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None
        assert result.label_group_id == label_group.label_group.label_group_id

    @pytest.mark.dependency(name="labels::permissions::editor_can_select_group", scope="session")
    def test_editor_can_select_group(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Editor Group")
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id
        )
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="labels::permissions::viewer_can_select_group", scope="session")
    def test_viewer_can_select_group(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Viewer Group")
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id
        )
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="labels::permissions::viewer_cannot_select_with_only_editors", scope="session")
    def test_viewer_cannot_select_with_only_editors(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        """Viewer should not be able to select when only_editors=True."""
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Viewer Group")
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id
        )
        q = label_group_mod_access_select(q, actor, only_editors=True)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="labels::permissions::editor_can_select_with_only_editors", scope="session")
    def test_editor_can_select_with_only_editors(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Editor Group")
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id
        )
        q = label_group_mod_access_select(q, actor, only_editors=True)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="labels::permissions::non_contributor_cannot_select_group", scope="session")
    def test_non_contributor_cannot_select_group(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_charlie")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id
        )
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="labels::permissions::admin_can_select_any_group", scope="session")
    def test_admin_can_select_any_group(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_admin")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id
        )
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="labels::permissions::cannot_select_group_on_private_novel", scope="session")
    def test_cannot_select_group_on_private_novel_without_access(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        """user_2 has no access to the private novel, so cannot see label group."""
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "Private Novel Group")
        q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id
        )
        q = label_group_mod_access_select(q, actor)
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
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id)
            .values(label_group_name="Updated Name")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, actor)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None
        assert result.label_group_name == "Updated Name"

    @pytest.mark.dependency(name="labels::permissions::editor_can_update", scope="session")
    def test_editor_can_update(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Editor Group")
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id)
            .values(label_group_name="Editor Updated")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, actor)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="labels::permissions::viewer_cannot_update", scope="session")
    def test_viewer_cannot_update(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Viewer Group")
        original_name = label_group.label_group.label_group_name
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id)
            .values(label_group_name="Should Not Update")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, actor)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None
        # Verify it wasn't updated
        test_db.refresh(label_group.label_group)
        assert label_group.label_group.label_group_name == original_name

    @pytest.mark.dependency(name="labels::permissions::non_contributor_cannot_update", scope="session")
    def test_non_contributor_cannot_update(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_charlie")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == label_group.label_group.label_group_id)
            .values(label_group_name="Hacked")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, actor)
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
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == label_group.label_data.label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="labels::permissions::editor_can_select_label_data", scope="session")
    def test_editor_can_select_label_data(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Editor Group")
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == label_group.label_data.label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="labels::permissions::viewer_can_select_label_data", scope="session")
    def test_viewer_can_select_label_data(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Viewer Group")
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == label_group.label_data.label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="labels::permissions::non_contributor_cannot_select_label_data", scope="session")
    def test_non_contributor_cannot_select_label_data(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_charlie")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == label_group.label_data.label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="labels::permissions::cannot_select_label_data_on_private_novel", scope="session")
    def test_cannot_select_label_data_on_private_novel(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        """user_2 cannot see label data on private novel they have no access to."""
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "Private Novel Group")
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == label_group.label_data.label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="labels::permissions::owner_can_select_aliased_label_data", scope="session")
    def test_owner_can_select_aliased_label_data(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        label_data_alias = aliased(label_models.LabelData)
        q = (
            select(label_data_alias)
            .join(
                label_models.LabelGroup,
                label_models.LabelGroup.label_group_id == label_data_alias.label_group_id,
            )
            .where(label_data_alias.label_data_id == label_group.label_data.label_data_id)
        )
        q = label_data_mod_access_select(q, actor, label_data_alias)

        result = test_db.execute(q).scalar_one_or_none()

        assert result is not None
        assert result.label_data_id == label_group.label_data.label_data_id

    @pytest.mark.dependency(name="labels::permissions::non_contributor_cannot_select_aliased_label_data", scope="session")
    def test_non_contributor_cannot_select_aliased_label_data(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_charlie")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        label_data_alias = aliased(label_models.LabelData)
        q = (
            select(label_data_alias)
            .join(
                label_models.LabelGroup,
                label_models.LabelGroup.label_group_id == label_data_alias.label_group_id,
            )
            .where(label_data_alias.label_data_id == label_group.label_data.label_data_id)
        )
        q = label_data_mod_access_select(q, actor, label_data_alias)

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
            "labels::permissions::owner_can_select_aliased_label_data",
            "labels::permissions::non_contributor_cannot_select_aliased_label_data",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestLabelUpdate:
    """Tests for label_mod_access_update."""

    @pytest.mark.dependency(name="labels::permissions::owner_can_update_labels", scope="session")
    def test_owner_can_update_labels(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        label_ids = [label.label_id for label in label_group.labels]
        stmt = (
            update(label_models.Label)
            .where(label_models.Label.label_id.in_(label_ids))
            .values(label_dirty=True)
            .returning(label_models.Label)
        )
        stmt = label_mod_access_update(stmt, actor)

        results = test_db.execute(stmt).scalars().all()
        test_db.commit()

        assert {label.label_id for label in results} == set(label_ids)

    @pytest.mark.dependency(name="labels::permissions::viewer_cannot_update_labels", scope="session")
    def test_viewer_cannot_update_labels(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Viewer Group")
        label_ids = [label.label_id for label in label_group.labels]
        stmt = (
            update(label_models.Label)
            .where(label_models.Label.label_id.in_(label_ids))
            .values(label_dirty=True)
            .returning(label_models.Label)
        )
        stmt = label_mod_access_update(stmt, actor)

        results = test_db.execute(stmt).scalars().all()
        test_db.commit()

        assert results == []

    @pytest.mark.dependency(name="labels::permissions::owner_can_update_aliased_labels", scope="session")
    def test_owner_can_update_aliased_labels(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        label_ids = [label.label_id for label in label_group.labels]
        label_alias = aliased(label_models.Label)
        stmt = (
            update(label_alias)
            .where(label_alias.label_id.in_(label_ids))
            .values(label_dirty=True)
            .returning(label_alias.label_id)
        )
        stmt = label_mod_access_update(stmt, actor, label_alias)

        result_ids = set(test_db.execute(stmt).scalars().all())
        test_db.commit()

        assert result_ids == set(label_ids)

    @pytest.mark.dependency(name="labels::permissions::label_editor_without_chapter_access_cannot_update", scope="session")
    def test_label_editor_without_chapter_access_cannot_update(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        private_group = _label_access_group(label_access_scenario, "Private Novel Group")
        private_label = label_models.Label(
            label_data_id=private_group.label_data.label_data_id,
            label_word="private",
            label_start=21,
            label_end=28,
            label_entity_group="MISC",
            label_score=0.95,
            label_dirty=False,
        )
        test_db.add_all(
            [
                label_models.LabelContributor(
                    label_group_id=private_group.label_group.label_group_id,
                    user_id=actor.user_id,
                    label_contributor_role=LabelRole.EDITOR,
                ),
                private_label,
            ]
        )
        test_db.commit()
        test_db.refresh(private_label)
        stmt = (
            update(label_models.Label)
            .where(label_models.Label.label_id == private_label.label_id)
            .values(label_dirty=True)
            .returning(label_models.Label)
        )
        stmt = label_mod_access_update(stmt, actor)

        results = test_db.execute(stmt).scalars().all()
        test_db.commit()
        test_db.refresh(private_label)

        assert results == []
        assert private_label.label_dirty is False

    @pytest.mark.dependency(
        name="gate::labels::permissions::label_update",
        depends=[
            "labels::permissions::owner_can_update_labels",
            "labels::permissions::viewer_cannot_update_labels",
            "labels::permissions::owner_can_update_aliased_labels",
            "labels::permissions::label_editor_without_chapter_access_cannot_update",
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
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_alice")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        label_ids = [label.label_id for label in label_group.labels]
        stmt = delete(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        stmt = label_mod_access_delete(stmt, actor)
        test_db.execute(stmt)
        test_db.commit()

        # Verify deleted
        remaining = (
            test_db.execute(select(label_models.Label).where(label_models.Label.label_id.in_(label_ids)))
            .scalars()
            .all()
        )
        assert len(remaining) == 0

    @pytest.mark.dependency(name="labels::permissions::editor_can_delete_labels", scope="session")
    def test_editor_can_delete_labels(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Editor Group")
        label_ids = [label.label_id for label in label_group.labels]
        stmt = delete(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        stmt = label_mod_access_delete(stmt, actor)
        test_db.execute(stmt)
        test_db.commit()

        remaining = (
            test_db.execute(select(label_models.Label).where(label_models.Label.label_id.in_(label_ids)))
            .scalars()
            .all()
        )
        assert len(remaining) == 0

    @pytest.mark.dependency(name="labels::permissions::viewer_cannot_delete_labels", scope="session")
    def test_viewer_cannot_delete_labels(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        label_group = _label_access_group(label_access_scenario, "With Viewer Group")
        label_ids = [label.label_id for label in label_group.labels]
        stmt = delete(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        stmt = label_mod_access_delete(stmt, actor)
        test_db.execute(stmt)
        test_db.commit()

        # Verify NOT deleted
        remaining = (
            test_db.execute(select(label_models.Label).where(label_models.Label.label_id.in_(label_ids)))
            .scalars()
            .all()
        )
        assert len(remaining) == len(label_group.labels)

    @pytest.mark.dependency(name="labels::permissions::non_contributor_cannot_delete_labels", scope="session")
    def test_non_contributor_cannot_delete_labels(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_charlie")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        label_ids = [label.label_id for label in label_group.labels]
        stmt = delete(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        stmt = label_mod_access_delete(stmt, actor)
        test_db.execute(stmt)
        test_db.commit()

        # Verify NOT deleted
        remaining = (
            test_db.execute(select(label_models.Label).where(label_models.Label.label_id.in_(label_ids)))
            .scalars()
            .all()
        )
        assert len(remaining) == len(label_group.labels)

    @pytest.mark.dependency(name="labels::permissions::admin_can_delete_any_labels", scope="session")
    def test_admin_can_delete_any_labels(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_admin")
        label_group = _label_access_group(label_access_scenario, "Owner Only Group")
        label_ids = [label.label_id for label in label_group.labels]
        stmt = delete(label_models.Label).where(label_models.Label.label_id.in_(label_ids))
        stmt = label_mod_access_delete(stmt, actor)
        test_db.execute(stmt)
        test_db.commit()

        remaining = (
            test_db.execute(select(label_models.Label).where(label_models.Label.label_id.in_(label_ids)))
            .scalars()
            .all()
        )
        assert len(remaining) == 0

    @pytest.mark.dependency(name="labels::permissions::label_editor_without_chapter_access_cannot_delete", scope="session")
    def test_label_editor_without_chapter_access_cannot_delete(
        self,
        test_db: Session,
        label_access_scenario: ScenarioBundle,
    ):
        actor = _label_access_user(label_access_scenario, "lp_bob")
        private_group = _label_access_group(label_access_scenario, "Private Novel Group")
        private_label = label_models.Label(
            label_data_id=private_group.label_data.label_data_id,
            label_word="private",
            label_start=21,
            label_end=28,
            label_entity_group="MISC",
            label_score=0.95,
            label_dirty=False,
        )
        test_db.add_all(
            [
                label_models.LabelContributor(
                    label_group_id=private_group.label_group.label_group_id,
                    user_id=actor.user_id,
                    label_contributor_role=LabelRole.EDITOR,
                ),
                private_label,
            ]
        )
        test_db.commit()
        test_db.refresh(private_label)
        stmt = delete(label_models.Label).where(label_models.Label.label_id == private_label.label_id)
        stmt = label_mod_access_delete(stmt, actor)

        test_db.execute(stmt)
        test_db.commit()

        remaining = test_db.execute(
            select(label_models.Label).where(label_models.Label.label_id == private_label.label_id)
        ).scalar_one_or_none()
        assert remaining is not None

    @pytest.mark.dependency(
        name="gate::labels::permissions::label_delete",
        depends=[
            "labels::permissions::owner_can_delete_labels",
            "labels::permissions::editor_can_delete_labels",
            "labels::permissions::viewer_cannot_delete_labels",
            "labels::permissions::non_contributor_cannot_delete_labels",
            "labels::permissions::admin_can_delete_any_labels",
            "labels::permissions::label_editor_without_chapter_access_cannot_delete",
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
        "gate::labels::permissions::label_update",
        "gate::labels::permissions::label_delete",
    ],
    scope="session",
)
def test_gate():
    """All labels permissions tests must pass before downstream layers run."""
    log_gate("gate::labels::permissions")
