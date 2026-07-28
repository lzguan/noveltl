"""
Tests for label permission functions.

Note: These tests are AI generated and may not cover all edge cases or be fully comprehensive. It is recommended to review and modify the tests as needed to ensure they align with the specific requirements and constraints of your application.
"""

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, aliased

from src.auth.models import User
from src.labels import models as label_models
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelData, LabelGroup
from src.labels.permissions import (
    label_data_mod_access_select,
    label_group_mod_access_select,
    label_group_mod_access_update,
    label_mod_access_delete,
    label_mod_access_update,
)
from test_support.test_data.scenarios import DatabaseScenario


def _label_access_user(scenario: DatabaseScenario, user_key: str) -> User:
    return scenario.users[user_key]


def _label_access_group(scenario: DatabaseScenario, group_key: str) -> LabelGroup:
    return scenario.label_groups[group_key]


def _label_data(scenario: DatabaseScenario, group: LabelGroup) -> LabelData:
    return next(data for data in scenario.label_datas.values() if data.label_group_id == group.label_group_id)


def _labels(scenario: DatabaseScenario, group: LabelGroup) -> list[Label]:
    data = _label_data(scenario, group)
    return [label for label in scenario.labels.values() if label.label_data_id == data.label_data_id]


class TestLabelGroupSelect:
    """Tests for label_group_mod_access_select."""

    def test_owner_can_select_own_group(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["owner"]
        label_group = label_access_scenario.label_groups["owner_only"]
        q = select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None
        assert result.label_group_id == label_group.label_group_id

    def test_editor_can_select_group(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_editor"]
        q = select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_can_select_group(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_viewer"]
        q = select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_select_with_only_editors(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        """Viewer should not be able to select when only_editors=True."""
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_viewer"]
        q = select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
        q = label_group_mod_access_select(q, actor, only_editors=True)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_editor_can_select_with_only_editors(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_editor"]
        q = select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
        q = label_group_mod_access_select(q, actor, only_editors=True)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_non_contributor_cannot_select_group(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["outsider"]
        label_group = label_access_scenario.label_groups["owner_only"]
        q = select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_admin_can_select_any_group(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["admin"]
        label_group = label_access_scenario.label_groups["owner_only"]
        q = select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_cannot_select_group_on_private_novel_without_access(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        """user_2 has no access to the private novel, so cannot see label group."""
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["private"]
        q = select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
        q = label_group_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None


class TestLabelGroupUpdate:
    """Tests for label_group_mod_access_update."""

    def test_owner_can_update(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["owner"]
        label_group = label_access_scenario.label_groups["owner_only"]
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
            .values(label_group_name="Updated Name")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, actor)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None
        assert result.label_group_name == "Updated Name"

    def test_editor_can_update(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_editor"]
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
            .values(label_group_name="Editor Updated")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, actor)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_update(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_viewer"]
        original_name = label_group.label_group_name
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
            .values(label_group_name="Should Not Update")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, actor)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None
        # Verify it wasn't updated
        test_db.refresh(label_group)
        assert label_group.label_group_name == original_name

    def test_non_contributor_cannot_update(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["outsider"]
        label_group = label_access_scenario.label_groups["owner_only"]
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
            .values(label_group_name="Hacked")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, actor)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None


class TestLabelDataSelect:
    """Tests for label_data_mod_access_select."""

    def test_owner_can_select_label_data(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["owner"]
        label_group = label_access_scenario.label_groups["owner_only"]
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == _label_data(label_access_scenario, label_group).label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_editor_can_select_label_data(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_editor"]
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == _label_data(label_access_scenario, label_group).label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_can_select_label_data(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_viewer"]
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == _label_data(label_access_scenario, label_group).label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_non_contributor_cannot_select_label_data(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["outsider"]
        label_group = label_access_scenario.label_groups["owner_only"]
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == _label_data(label_access_scenario, label_group).label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_cannot_select_label_data_on_private_novel(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        """user_2 cannot see label data on private novel they have no access to."""
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["private"]
        q = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == _label_data(label_access_scenario, label_group).label_data_id
        )
        q = label_data_mod_access_select(q, actor)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_owner_can_select_aliased_label_data(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["owner"]
        label_group = label_access_scenario.label_groups["owner_only"]
        label_data_alias = aliased(label_models.LabelData)
        q = (
            select(label_data_alias)
            .join(
                label_models.LabelGroup,
                label_models.LabelGroup.label_group_id == label_data_alias.label_group_id,
            )
            .where(label_data_alias.label_data_id == _label_data(label_access_scenario, label_group).label_data_id)
        )
        q = label_data_mod_access_select(q, actor, label_data_alias)

        result = test_db.execute(q).scalar_one_or_none()

        assert result is not None
        assert result.label_data_id == _label_data(label_access_scenario, label_group).label_data_id

    def test_non_contributor_cannot_select_aliased_label_data(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["outsider"]
        label_group = label_access_scenario.label_groups["owner_only"]
        label_data_alias = aliased(label_models.LabelData)
        q = (
            select(label_data_alias)
            .join(
                label_models.LabelGroup,
                label_models.LabelGroup.label_group_id == label_data_alias.label_group_id,
            )
            .where(label_data_alias.label_data_id == _label_data(label_access_scenario, label_group).label_data_id)
        )
        q = label_data_mod_access_select(q, actor, label_data_alias)

        result = test_db.execute(q).scalar_one_or_none()

        assert result is None


class TestLabelUpdate:
    """Tests for label_mod_access_update."""

    def test_owner_can_update_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["owner"]
        label_group = label_access_scenario.label_groups["owner_only"]
        label_ids = [label.label_id for label in _labels(label_access_scenario, label_group)]
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

    def test_viewer_cannot_update_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_viewer"]
        label_ids = [label.label_id for label in _labels(label_access_scenario, label_group)]
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

    def test_owner_can_update_aliased_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["owner"]
        label_group = label_access_scenario.label_groups["owner_only"]
        label_ids = [label.label_id for label in _labels(label_access_scenario, label_group)]
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

    def test_label_editor_without_chapter_access_cannot_update(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        private_group = label_access_scenario.label_groups["private"]
        private_label = label_models.Label(
            label_data_id=_label_data(label_access_scenario, private_group).label_data_id,
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
                    label_group_id=private_group.label_group_id,
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


class TestLabelDelete:
    """Tests for label_mod_access_delete."""

    def test_owner_can_delete_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["owner"]
        label_group = label_access_scenario.label_groups["owner_only"]
        label_ids = [label.label_id for label in _labels(label_access_scenario, label_group)]
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

    def test_editor_can_delete_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_editor"]
        label_ids = [label.label_id for label in _labels(label_access_scenario, label_group)]
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

    def test_viewer_cannot_delete_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        label_group = label_access_scenario.label_groups["with_viewer"]
        label_ids = [label.label_id for label in _labels(label_access_scenario, label_group)]
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
        assert len(remaining) == len(_labels(label_access_scenario, label_group))

    def test_non_contributor_cannot_delete_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["outsider"]
        label_group = label_access_scenario.label_groups["owner_only"]
        label_ids = [label.label_id for label in _labels(label_access_scenario, label_group)]
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
        assert len(remaining) == len(_labels(label_access_scenario, label_group))

    def test_admin_can_delete_any_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["admin"]
        label_group = label_access_scenario.label_groups["owner_only"]
        label_ids = [label.label_id for label in _labels(label_access_scenario, label_group)]
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

    def test_label_editor_without_chapter_access_cannot_delete(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["collaborator"]
        private_group = label_access_scenario.label_groups["private"]
        private_label = label_models.Label(
            label_data_id=_label_data(label_access_scenario, private_group).label_data_id,
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
                    label_group_id=private_group.label_group_id,
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
