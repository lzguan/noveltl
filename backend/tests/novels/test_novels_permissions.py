"""
Tests for novel permission functions in novels/permissions.py.

Tests the permission helpers directly by applying them to raw SQLAlchemy
statements and verifying which rows are returned/affected for each user role.
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session, aliased

from src.novels.models import Chapter, ChapterContent, Novel
from src.novels.permissions import (
    chapter_content_mod_access_insert,
    chapter_content_mod_access_select,
    chapter_mod_access_insert,
    chapter_mod_access_select,
    chapter_mod_access_update,
    novel_mod_access_select,
    novel_mod_access_update,
)
from test_support.test_data.scenarios import DatabaseScenario


def test_novel_mod_access_select(test_db: Session, novel_permission_scenario: DatabaseScenario) -> None:
    s = novel_permission_scenario

    guest_ids = {n.novel_id for n in test_db.execute(novel_mod_access_select(select(Novel), None)).scalars().all()}
    assert {s.novels["put"].novel_id, s.novels["ut"].novel_id} <= guest_ids
    assert s.novels["rt"].novel_id not in guest_ids
    assert s.novels["prt"].novel_id not in guest_ids

    cases = (
        ("put", "other", False, True),
        ("rt", "other", False, False),
        ("prt", "other", False, False),
        ("rt", "owner", False, True),
        ("prt", "owner", False, True),
        ("prt", "admin", False, True),
        ("rt", "admin", False, True),
        ("oe", "other", False, True),
        ("ov", "other", False, True),
        ("oe", "other", True, True),
        ("ov", "other", True, False),
        ("put", None, True, False),
    )
    for novel_key, user_key, edit_only, expected in cases:
        actor = None if user_key is None else s.users[user_key]
        q = novel_mod_access_select(
            select(Novel).where(Novel.novel_id == s.novels[novel_key].novel_id),
            actor,
            edit_only=edit_only,
        )
        assert (test_db.execute(q).scalar_one_or_none() is not None) is expected, (
            novel_key,
            user_key,
            edit_only,
        )


def test_novel_mod_access_update(test_db: Session, novel_permission_scenario: DatabaseScenario) -> None:
    s = novel_permission_scenario

    for novel_key, user_key, expected in (
        ("put", "owner", True),
        ("oe", "other", True),
        ("ov", "other", False),
        ("put", "other", False),
        ("prt", "admin", True),
    ):
        stmt = novel_mod_access_update(
            update(Novel)
            .where(Novel.novel_id == s.novels[novel_key].novel_id)
            .values(novel_description=f"updated by {user_key}")
            .returning(Novel.novel_id),
            s.users[user_key],
        )
        assert (test_db.execute(stmt).scalar_one_or_none() is not None) is expected, (novel_key, user_key)
        test_db.rollback()

    novel_alias = aliased(Novel)
    aliased_stmt = novel_mod_access_update(
        update(novel_alias)
        .where(novel_alias.novel_id == s.novels["put"].novel_id)
        .values(novel_description="aliased update")
        .returning(novel_alias.novel_id),
        s.users["owner"],
        novel_alias,
    )
    assert test_db.execute(aliased_stmt).scalar_one_or_none() == s.novels["put"].novel_id
    test_db.rollback()


def test_chapter_mod_access_select(test_db: Session, novel_permission_scenario: DatabaseScenario) -> None:
    s = novel_permission_scenario

    cases = (
        ("public", None, False, True),
        ("restricted", None, False, False),
        ("private", None, False, False),
        ("restricted", "owner", False, True),
        ("private", "other", False, False),
        ("private", "admin", False, True),
        ("owner_editor", "other", True, True),
        ("owner_viewer", "other", True, False),
    )
    for chapter_key, user_key, edit_only, expected in cases:
        actor = None if user_key is None else s.users[user_key]
        q = chapter_mod_access_select(
            select(Chapter).where(Chapter.chapter_id == s.chapters[chapter_key].chapter_id),
            actor,
            edit_only=edit_only,
        )
        assert (test_db.execute(q).scalar_one_or_none() is not None) is expected, (
            chapter_key,
            user_key,
            edit_only,
        )


def test_chapter_mod_access_insert(test_db: Session, novel_permission_scenario: DatabaseScenario) -> None:
    s = novel_permission_scenario

    for novel_key, user_key, expected in (
        ("rt", "owner", True),
        ("oe", "other", True),
        ("ov", "other", False),
        ("prt", "other", False),
        ("prt", "admin", True),
    ):
        q = chapter_mod_access_insert(select(1), s.users[user_key], s.novels[novel_key].novel_id)
        assert (test_db.execute(q).scalar_one_or_none() is not None) is expected, (novel_key, user_key)


def test_chapter_mod_access_update(test_db: Session, novel_permission_scenario: DatabaseScenario) -> None:
    s = novel_permission_scenario

    for chapter_key, user_key, expected in (
        ("restricted", "owner", True),
        ("owner_editor", "other", True),
        ("owner_viewer", "other", False),
        ("private", "other", False),
        ("private", "admin", True),
    ):
        stmt = chapter_mod_access_update(
            update(Chapter)
            .where(Chapter.chapter_id == s.chapters[chapter_key].chapter_id)
            .values(chapter_num=99)
            .returning(Chapter.chapter_id),
            s.users[user_key],
        )
        assert (test_db.execute(stmt).scalar_one_or_none() is not None) is expected, (chapter_key, user_key)
        test_db.rollback()

    chapter_alias = aliased(Chapter)
    aliased_stmt = chapter_mod_access_update(
        update(chapter_alias)
        .where(chapter_alias.chapter_id == s.chapters["restricted"].chapter_id)
        .values(chapter_title="Aliased Chapter")
        .returning(chapter_alias.chapter_id),
        s.users["owner"],
        chapter_alias,
    )
    assert test_db.execute(aliased_stmt).scalar_one_or_none() == s.chapters["restricted"].chapter_id
    test_db.rollback()


def test_chapter_content_mod_access_select(test_db: Session, novel_permission_scenario: DatabaseScenario) -> None:
    s = novel_permission_scenario

    cases = (
        ("public_v1", None, False, True),
        ("restricted_v1", None, False, False),
        ("private_v1", None, False, False),
        ("restricted_v1", "owner", False, True),
        ("private_v1", "owner", False, True),
        ("private_v1", "other", False, False),
        ("private_v1", "admin", False, True),
        ("restricted_v1", "admin", False, True),
        ("owner_editor_v1", "other", False, True),
        ("owner_viewer_v1", "other", False, True),
        ("owner_editor_v1", "other", True, True),
        ("owner_viewer_v1", "other", True, False),
    )
    for content_key, user_key, edit_only, expected in cases:
        actor = None if user_key is None else s.users[user_key]
        q = chapter_content_mod_access_select(
            select(ChapterContent).where(
                ChapterContent.chapter_content_id == s.contents[content_key].chapter_content_id
            ),
            actor,
            edit_only=edit_only,
        )
        assert (test_db.execute(q).scalar_one_or_none() is not None) is expected, (
            content_key,
            user_key,
            edit_only,
        )

    content_alias = aliased(ChapterContent)
    private_id = s.contents["private_v1"].chapter_content_id
    for user_key, expected in (("owner", True), ("other", False)):
        q = chapter_content_mod_access_select(
            select(content_alias).where(content_alias.chapter_content_id == private_id),
            s.users[user_key],
            content_alias,
        )
        assert (test_db.execute(q).scalar_one_or_none() is not None) is expected, user_key


def test_chapter_content_mod_access_insert(test_db: Session, novel_permission_scenario: DatabaseScenario) -> None:
    s = novel_permission_scenario

    for chapter_key, user_key, expected in (
        ("restricted", "owner", True),
        ("owner_editor", "other", True),
        ("owner_viewer", "other", False),
        ("private", "other", False),
        ("private", "admin", True),
    ):
        q = chapter_content_mod_access_insert(select(1), s.users[user_key], s.chapters[chapter_key].chapter_id)
        assert (test_db.execute(q).scalar_one_or_none() is not None) is expected, (chapter_key, user_key)
