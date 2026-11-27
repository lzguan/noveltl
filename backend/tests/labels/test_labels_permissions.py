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


def test_label_group_mod_access_select(test_db: Session, label_access_scenario: DatabaseScenario) -> None:
    s = label_access_scenario
    cases = (
        ("owner", "owner_only", False, True),
        ("owner", "private", False, True),
        ("editor", "owner_only", False, True),
        ("editor", "owner_only", True, True),
        ("editor", "private", False, True),
        ("editor", "private", True, True),
        ("viewer", "owner_only", False, True),
        ("viewer", "owner_only", True, False),
        ("viewer", "private", False, True),
        ("viewer", "private", True, False),
        ("outsider", "owner_only", False, True),
        ("outsider", "owner_only", True, False),
        ("outsider", "private", False, False),
        ("admin", "owner_only", True, True),
        ("admin", "private", True, True),
    )
    for user_key, group_key, edit_only, expected in cases:
        group = s.label_groups[group_key]
        q = label_group_mod_access_select(
            select(label_models.LabelGroup).where(label_models.LabelGroup.label_group_id == group.label_group_id),
            s.users[user_key],
            edit_only=edit_only,
        )
        assert (test_db.execute(q).scalar_one_or_none() is not None) is expected, (user_key, group_key, edit_only)


def test_label_group_mod_access_insert(test_db: Session, label_access_scenario: DatabaseScenario) -> None:
    s = label_access_scenario
    for user_key, novel_key, expected in (
        ("owner", "private", True),
        ("editor", "private", True),
        ("admin", "private", True),
        ("viewer", "public", False),
        ("outsider", "public", False),
    ):
        q = label_group_mod_access_insert(select(literal(1)), s.users[user_key], s.novels[novel_key].novel_id)
        assert (test_db.execute(q).scalar_one_or_none() == 1) is expected, (user_key, novel_key)


def test_label_group_mod_access_update(test_db: Session, label_access_scenario: DatabaseScenario) -> None:
    s = label_access_scenario
    for user_key, group_key, expected in (
        ("owner", "owner_only", True),
        ("editor", "private", True),
        ("viewer", "with_viewer", False),
        ("outsider", "owner_only", False),
    ):
        group = s.label_groups[group_key]
        stmt = label_group_mod_access_update(
            update(label_models.LabelGroup)
            .where(label_models.LabelGroup.label_group_id == group.label_group_id)
            .values(label_group_name="Updated")
            .returning(label_models.LabelGroup.label_group_id),
            s.users[user_key],
        )
        assert (test_db.execute(stmt).scalar_one_or_none() is not None) is expected, (user_key, group_key)
        test_db.rollback()


def test_label_data_mod_access_select(test_db: Session, label_access_scenario: DatabaseScenario) -> None:
    s = label_access_scenario
    public_group = s.label_groups["owner_only"]
    private_group = s.label_groups["private"]

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

    public_data_id = _label_data(s, public_group).label_data_id
    editor_data_id = _label_data(s, s.label_groups["with_editor"]).label_data_id
    private_data_id = _label_data(s, private_group).label_data_id

    for user_key in ("owner", "editor", "viewer", "admin"):
        for data_id in (public_data_id, private_data_id):
            q = label_data_mod_access_select(
                select(label_models.LabelData).where(label_models.LabelData.label_data_id == data_id),
                s.users[user_key],
            )
            assert test_db.execute(q).scalar_one_or_none() is not None

    for user_key, expected in (("editor", True), ("viewer", False), ("outsider", False)):
        q = label_data_mod_access_select(
            select(label_models.LabelData).where(label_models.LabelData.label_data_id == editor_data_id),
            s.users[user_key],
            edit_only=True,
        )
        assert (test_db.execute(q).scalar_one_or_none() is not None) is expected

    outsider = s.users["outsider"]
    for data_id, expected in ((public_data_id, True), (draft_data.label_data_id, False), (private_data_id, False)):
        q = label_data_mod_access_select(
            select(label_models.LabelData).where(label_models.LabelData.label_data_id == data_id),
            outsider,
        )
        assert (test_db.execute(q).scalar_one_or_none() is not None) is expected

    label_data_alias = aliased(label_models.LabelData)
    base = (
        select(label_data_alias)
        .join(label_models.LabelGroup, label_models.LabelGroup.label_group_id == label_data_alias.label_group_id)
        .where(label_data_alias.label_data_id == private_data_id)
    )
    assert (
        test_db.execute(label_data_mod_access_select(base, s.users["owner"], label_data_alias)).scalar_one_or_none()
        is not None
    )
    assert (
        test_db.execute(label_data_mod_access_select(base, outsider, label_data_alias)).scalar_one_or_none() is None
    )


def test_label_data_mod_access_insert(test_db: Session, label_access_scenario: DatabaseScenario) -> None:
    s = label_access_scenario
    for user_key, group_key, expected in (
        ("owner", "private", True),
        ("editor", "private", True),
        ("admin", "private", True),
        ("viewer", "with_editor", False),
        ("outsider", "with_editor", False),
    ):
        q = label_data_mod_access_insert(
            select(literal(1)),
            s.users[user_key],
            s.label_groups[group_key].label_group_id,
        )
        assert (test_db.execute(q).scalar_one_or_none() == 1) is expected, (user_key, group_key)


def test_label_mod_access_update(test_db: Session, label_access_scenario: DatabaseScenario) -> None:
    s = label_access_scenario

    for user_key, label_ids, expected in (
        ("viewer", [label.label_id for label in _labels(s, s.label_groups["with_viewer"])], False),
        ("outsider", [s.labels["editor_test"].label_id, s.labels["private_test"].label_id], False),
        ("owner", [label.label_id for label in _labels(s, s.label_groups["owner_only"])], True),
        ("editor", [label.label_id for label in _labels(s, s.label_groups["private"])], True),
    ):
        stmt = label_mod_access_update(
            update(label_models.Label)
            .where(label_models.Label.label_id.in_(label_ids))
            .values(label_dirty=True)
            .returning(label_models.Label.label_id),
            s.users[user_key],
        )
        returned = set(test_db.execute(stmt).scalars().all())
        assert returned == (set(label_ids) if expected else set()), user_key
        test_db.rollback()

    owner_ids = [label.label_id for label in _labels(s, s.label_groups["owner_only"])]
    label_alias = aliased(label_models.Label)
    aliased_stmt = label_mod_access_update(
        update(label_alias)
        .where(label_alias.label_id.in_(owner_ids))
        .values(label_dirty=True)
        .returning(label_alias.label_id),
        s.users["owner"],
        label_alias,
    )
    assert set(test_db.execute(aliased_stmt).scalars().all()) == set(owner_ids)
    test_db.rollback()


def test_label_mod_access_delete(test_db: Session, label_access_scenario: DatabaseScenario) -> None:
    s = label_access_scenario

    for user_key, group_key, expected_deleted in (
        ("viewer", "with_viewer", False),
        ("outsider", "owner_only", False),
        ("owner", "owner_only", True),
        ("editor", "private", True),
        ("admin", "private", True),
    ):
        label_ids = [label.label_id for label in _labels(s, s.label_groups[group_key])]
        stmt = label_mod_access_delete(
            delete(label_models.Label).where(label_models.Label.label_id.in_(label_ids)),
            s.users[user_key],
        )
        test_db.execute(stmt)
        remaining = test_db.execute(
            select(label_models.Label.label_id).where(label_models.Label.label_id.in_(label_ids))
        ).scalars().all()
        assert len(remaining) == (0 if expected_deleted else len(label_ids)), (user_key, group_key)
        test_db.rollback()
