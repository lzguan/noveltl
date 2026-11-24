"""
Tests for label permission functions.
"""

from sqlalchemy import delete, literal, select, update
from sqlalchemy.orm import Session, aliased

from src.labels import models as label_models
from src.labels.models import Label, LabelData, LabelGroup
from src.labels.permissions import (
    label_data_mod_access_insert,
    label_data_mod_access_select,
    label_group_mod_access_insert,
    label_group_mod_access_select,
    label_group_mod_access_update,
    label_mod_access_delete,
    label_mod_access_update,
)
from src.novels.models import Chapter, ChapterContent
from test_support.test_data.scenarios import DatabaseScenario


def _label_data(scenario: DatabaseScenario, group: LabelGroup) -> LabelData:
    return next(data for data in scenario.label_datas.values() if data.label_group_id == group.label_group_id)


def _labels(scenario: DatabaseScenario, group: LabelGroup) -> list[Label]:
    data = _label_data(scenario, group)
    return [label for label in scenario.labels.values() if label.label_data_id == data.label_data_id]


class TestLabelGroupSelect:
    def test_owner_can_select_public_and_private_groups(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["owner"]
        for group_key in ("owner_only", "private"):
            label_group = label_access_scenario.label_groups[group_key]
            q = select(label_models.LabelGroup).where(
                label_models.LabelGroup.label_group_id == label_group.label_group_id
            )
            q = label_group_mod_access_select(q, actor)
            result = test_db.execute(q).scalar_one_or_none()
            assert result is not None
            assert result.label_group_id == label_group.label_group_id

    def test_novel_editor_can_select_groups(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["editor"]
        for group_key in ("owner_only", "private"):
            label_group = label_access_scenario.label_groups[group_key]
            for edit_only in (False, True):
                q = select(label_models.LabelGroup).where(
                    label_models.LabelGroup.label_group_id == label_group.label_group_id
                )
                q = label_group_mod_access_select(q, actor, edit_only=edit_only)
                assert test_db.execute(q).scalar_one_or_none() is not None

    def test_novel_viewer_can_read_but_cannot_select_for_edit(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["viewer"]
        for group_key in ("owner_only", "private"):
            label_group = label_access_scenario.label_groups[group_key]
            base = select(label_models.LabelGroup).where(
                label_models.LabelGroup.label_group_id == label_group.label_group_id
            )
            assert test_db.execute(label_group_mod_access_select(base, actor)).scalar_one_or_none() is not None
            assert (
                test_db.execute(label_group_mod_access_select(base, actor, edit_only=True)).scalar_one_or_none() is None
            )

    def test_outsider_can_read_public_group_only(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["outsider"]
        public_group = label_access_scenario.label_groups["owner_only"]
        private_group = label_access_scenario.label_groups["private"]

        public_q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == public_group.label_group_id
        )
        private_q = select(label_models.LabelGroup).where(
            label_models.LabelGroup.label_group_id == private_group.label_group_id
        )
        assert test_db.execute(label_group_mod_access_select(public_q, actor)).scalar_one_or_none() is not None
        assert (
            test_db.execute(label_group_mod_access_select(public_q, actor, edit_only=True)).scalar_one_or_none() is None
        )
        assert test_db.execute(label_group_mod_access_select(private_q, actor)).scalar_one_or_none() is None

    def test_admin_can_select_any_group(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["admin"]
        for group_key in ("owner_only", "private"):
            label_group = label_access_scenario.label_groups[group_key]
            q = select(label_models.LabelGroup).where(
                label_models.LabelGroup.label_group_id == label_group.label_group_id
            )
            q = label_group_mod_access_select(q, actor, edit_only=True)
            assert test_db.execute(q).scalar_one_or_none() is not None


class TestLabelGroupInsert:
    def test_owner_editor_and_admin_can_insert(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        novel = label_access_scenario.novels["private"]
        for user_key in ("owner", "editor", "admin"):
            q = label_group_mod_access_insert(select(literal(1)), label_access_scenario.users[user_key], novel.novel_id)
            assert test_db.execute(q).scalar_one_or_none() == 1

    def test_viewer_and_outsider_cannot_insert(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        novel = label_access_scenario.novels["public"]
        for user_key in ("viewer", "outsider"):
            q = label_group_mod_access_insert(select(literal(1)), label_access_scenario.users[user_key], novel.novel_id)
            assert test_db.execute(q).scalar_one_or_none() is None


class TestLabelGroupUpdate:
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

    def test_novel_editor_can_update_without_label_contributor(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["editor"]
        label_group = label_access_scenario.label_groups["private"]
        stmt = (
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
            .values(label_group_name="Editor Updated")
            .returning(label_models.LabelGroup)
        )
        stmt = label_group_mod_access_update(stmt, actor)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None
        assert result.label_group_name == "Editor Updated"

    def test_viewer_cannot_update(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["viewer"]
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
        test_db.refresh(label_group)
        assert label_group.label_group_name == original_name

    def test_outsider_and_label_only_contributor_cannot_update(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        for user_key, group_key in (("outsider", "owner_only"), ("collaborator", "with_editor")):
            actor = label_access_scenario.users[user_key]
            label_group = label_access_scenario.label_groups[group_key]
            stmt = (
                update(label_models.LabelGroup)
                .where(label_models.LabelGroup.label_group_id == label_group.label_group_id)
                .values(label_group_name="Hacked")
                .returning(label_models.LabelGroup)
            )
            stmt = label_group_mod_access_update(stmt, actor)
            assert test_db.execute(stmt).scalar_one_or_none() is None


class TestLabelDataSelect:
    def test_owner_editor_viewer_and_admin_can_select_public_and_private_label_data(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        for user_key in ("owner", "editor", "viewer", "admin"):
            actor = label_access_scenario.users[user_key]
            for group_key in ("owner_only", "private"):
                label_group = label_access_scenario.label_groups[group_key]
                q = select(label_models.LabelData).where(
                    label_models.LabelData.label_data_id
                    == _label_data(label_access_scenario, label_group).label_data_id
                )
                q = label_data_mod_access_select(q, actor)
                assert test_db.execute(q).scalar_one_or_none() is not None

    def test_edit_only_allows_novel_editor_and_denies_viewer_and_outsider(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        label_group = label_access_scenario.label_groups["with_editor"]
        base = select(label_models.LabelData).where(
            label_models.LabelData.label_data_id == _label_data(label_access_scenario, label_group).label_data_id
        )

        editor = label_access_scenario.users["editor"]
        assert test_db.execute(label_data_mod_access_select(base, editor, edit_only=True)).scalar_one_or_none()

        for denied_key in ("viewer", "outsider"):
            actor = label_access_scenario.users[denied_key]
            assert (
                test_db.execute(label_data_mod_access_select(base, actor, edit_only=True)).scalar_one_or_none() is None
            )

    def test_outsider_can_select_public_chapter_only(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["outsider"]
        public_group = label_access_scenario.label_groups["owner_only"]
        private_group = label_access_scenario.label_groups["private"]

        draft_chapter = Chapter(
            novel_id=public_group.novel_id,
            chapter_num=2,
            chapter_title="Draft",
            chapter_is_public=False,
        )
        test_db.add(draft_chapter)
        test_db.flush()
        draft_content = ChapterContent(
            chapter_id=draft_chapter.chapter_id,
            chapter_content_version=1,
            chapter_content_text="Draft chapter text.",
        )
        test_db.add(draft_content)
        test_db.flush()
        draft_data = LabelData(
            label_group_id=public_group.label_group_id,
            chapter_content_id=draft_content.chapter_content_id,
        )
        test_db.add(draft_data)
        test_db.commit()

        public_q = label_data_mod_access_select(
            select(label_models.LabelData).where(
                label_models.LabelData.label_data_id == _label_data(label_access_scenario, public_group).label_data_id
            ),
            actor,
        )
        draft_q = label_data_mod_access_select(
            select(label_models.LabelData).where(label_models.LabelData.label_data_id == draft_data.label_data_id),
            actor,
        )
        private_q = label_data_mod_access_select(
            select(label_models.LabelData).where(
                label_models.LabelData.label_data_id == _label_data(label_access_scenario, private_group).label_data_id
            ),
            actor,
        )

        assert test_db.execute(public_q).scalar_one_or_none() is not None
        assert test_db.execute(draft_q).scalar_one_or_none() is None
        assert test_db.execute(private_q).scalar_one_or_none() is None

    def test_aliased_label_data_select_respects_novel_access(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        private_group = label_access_scenario.label_groups["private"]
        private_data_id = _label_data(label_access_scenario, private_group).label_data_id
        label_data_alias = aliased(label_models.LabelData)
        base = (
            select(label_data_alias)
            .join(
                label_models.LabelGroup,
                label_models.LabelGroup.label_group_id == label_data_alias.label_group_id,
            )
            .where(label_data_alias.label_data_id == private_data_id)
        )

        owner_result = test_db.execute(
            label_data_mod_access_select(base, label_access_scenario.users["owner"], label_data_alias)
        ).scalar_one_or_none()
        outsider_result = test_db.execute(
            label_data_mod_access_select(base, label_access_scenario.users["outsider"], label_data_alias)
        ).scalar_one_or_none()

        assert owner_result is not None
        assert owner_result.label_data_id == private_data_id
        assert outsider_result is None


class TestLabelDataInsert:
    def test_owner_editor_and_admin_can_insert(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        group = label_access_scenario.label_groups["private"]
        for user_key in ("owner", "editor", "admin"):
            q = label_data_mod_access_insert(
                select(literal(1)), label_access_scenario.users[user_key], group.label_group_id
            )
            assert test_db.execute(q).scalar_one_or_none() == 1

    def test_viewer_outsider_and_label_only_editor_cannot_insert(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        group = label_access_scenario.label_groups["with_editor"]
        for user_key in ("viewer", "outsider", "collaborator"):
            q = label_data_mod_access_insert(
                select(literal(1)), label_access_scenario.users[user_key], group.label_group_id
            )
            assert test_db.execute(q).scalar_one_or_none() is None


class TestLabelUpdate:
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

    def test_novel_editor_can_update_labels_without_label_contributor(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["editor"]
        label_group = label_access_scenario.label_groups["private"]
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
        actor = label_access_scenario.users["viewer"]
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

    def test_outsider_cannot_update_public_or_private_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["outsider"]
        public_label = label_access_scenario.labels["editor_test"]
        private_label = label_access_scenario.labels["private_test"]

        for target in (public_label, private_label):
            stmt = (
                update(label_models.Label)
                .where(label_models.Label.label_id == target.label_id)
                .values(label_dirty=True)
                .returning(label_models.Label)
            )
            stmt = label_mod_access_update(stmt, actor)
            results = test_db.execute(stmt).scalars().all()
            test_db.commit()
            test_db.refresh(target)

            assert results == []
            assert target.label_dirty is False


class TestLabelDelete:
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

        remaining = (
            test_db.execute(select(label_models.Label).where(label_models.Label.label_id.in_(label_ids)))
            .scalars()
            .all()
        )
        assert len(remaining) == 0

    def test_novel_editor_can_delete_labels_without_label_contributor(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["editor"]
        label_group = label_access_scenario.label_groups["private"]
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
        actor = label_access_scenario.users["viewer"]
        label_group = label_access_scenario.label_groups["with_viewer"]
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
        assert len(remaining) == len(label_ids)

    def test_outsider_cannot_delete_labels(
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

        remaining = (
            test_db.execute(select(label_models.Label).where(label_models.Label.label_id.in_(label_ids)))
            .scalars()
            .all()
        )
        assert len(remaining) == len(label_ids)

    def test_admin_can_delete_any_labels(
        self,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ):
        actor = label_access_scenario.users["admin"]
        label_group = label_access_scenario.label_groups["private"]
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
