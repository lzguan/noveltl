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

# ============================================================
# novel_mod_access_select
# ============================================================


class TestNovelModAccessSelect:
    def test_guest_sees_public_and_unlisted(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Novel)
        q = novel_mod_access_select(q, None)
        results = test_db.execute(q).scalars().all()
        ids = {n.novel_id for n in results}
        assert novel_permission_scenario.novels["put"].novel_id in ids
        assert novel_permission_scenario.novels["ut"].novel_id in ids
        assert novel_permission_scenario.novels["rt"].novel_id not in ids
        assert novel_permission_scenario.novels["prt"].novel_id not in ids

    def test_non_contributor_sees_public_and_unlisted(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(Novel).where(
            Novel.novel_id.in_(
                [
                    novel_permission_scenario.novels["put"].novel_id,
                    novel_permission_scenario.novels["rt"].novel_id,
                    novel_permission_scenario.novels["prt"].novel_id,
                ]
            )
        )
        q = novel_mod_access_select(q, novel_permission_scenario.users["other"])
        results = test_db.execute(q).scalars().all()
        ids = {n.novel_id for n in results}
        assert novel_permission_scenario.novels["put"].novel_id in ids
        assert novel_permission_scenario.novels["rt"].novel_id not in ids
        assert novel_permission_scenario.novels["prt"].novel_id not in ids

    def test_contributor_sees_own_restricted(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Novel).where(Novel.novel_id == novel_permission_scenario.novels["rt"].novel_id)
        q = novel_mod_access_select(q, novel_permission_scenario.users["owner"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_contributor_sees_own_private(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Novel).where(Novel.novel_id == novel_permission_scenario.novels["prt"].novel_id)
        q = novel_mod_access_select(q, novel_permission_scenario.users["owner"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_admin_sees_everything(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Novel).where(
            Novel.novel_id.in_(
                [
                    novel_permission_scenario.novels["prt"].novel_id,
                    novel_permission_scenario.novels["rt"].novel_id,
                ]
            )
        )
        q = novel_mod_access_select(q, novel_permission_scenario.users["admin"])
        results = test_db.execute(q).scalars().all()
        assert len(results) == 2

    def test_editor_sees_private_novel(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Novel).where(Novel.novel_id == novel_permission_scenario.novels["oe"].novel_id)
        q = novel_mod_access_select(q, novel_permission_scenario.users["other"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_sees_private_novel(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Novel).where(Novel.novel_id == novel_permission_scenario.novels["ov"].novel_id)
        q = novel_mod_access_select(q, novel_permission_scenario.users["other"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_edit_only_allows_editor(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Novel).where(Novel.novel_id == novel_permission_scenario.novels["oe"].novel_id)
        q = novel_mod_access_select(q, novel_permission_scenario.users["other"], edit_only=True)

        assert test_db.execute(q).scalar_one_or_none() is not None

    def test_edit_only_denies_viewer(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Novel).where(Novel.novel_id == novel_permission_scenario.novels["ov"].novel_id)
        q = novel_mod_access_select(q, novel_permission_scenario.users["other"], edit_only=True)

        assert test_db.execute(q).scalar_one_or_none() is None

    def test_edit_only_denies_guest(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Novel).where(Novel.novel_id == novel_permission_scenario.novels["put"].novel_id)
        q = novel_mod_access_select(q, None, edit_only=True)

        assert test_db.execute(q).scalar_one_or_none() is None


# ============================================================
# novel_mod_access_update
# ============================================================


class TestNovelModAccessUpdate:
    def test_owner_can_update(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == novel_permission_scenario.novels["put"].novel_id)
            .values(novel_description="updated")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, novel_permission_scenario.users["owner"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_editor_can_update(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == novel_permission_scenario.novels["oe"].novel_id)
            .values(novel_description="editor update")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, novel_permission_scenario.users["other"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_update(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == novel_permission_scenario.novels["ov"].novel_id)
            .values(novel_description="viewer update")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, novel_permission_scenario.users["other"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    def test_non_contributor_cannot_update(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == novel_permission_scenario.novels["put"].novel_id)
            .values(novel_description="hacked")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, novel_permission_scenario.users["other"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    def test_admin_can_update_any(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == novel_permission_scenario.novels["prt"].novel_id)
            .values(novel_description="admin")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, novel_permission_scenario.users["admin"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_owner_can_update_aliased_novel(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        novel_alias = aliased(Novel)
        stmt = (
            update(novel_alias)
            .where(novel_alias.novel_id == novel_permission_scenario.novels["put"].novel_id)
            .values(novel_description="aliased update")
            .returning(novel_alias.novel_id)
        )
        stmt = novel_mod_access_update(stmt, novel_permission_scenario.users["owner"], novel_alias)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result == novel_permission_scenario.novels["put"].novel_id


# ============================================================
# chapter_mod_access_select
# ============================================================


class TestChapterModAccessSelect:
    def test_guest_sees_chapter_on_public_novel(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Chapter).where(Chapter.chapter_id == novel_permission_scenario.chapters["public"].chapter_id)
        q = chapter_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_guest_cannot_see_chapter_on_restricted_novel(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(Chapter).where(Chapter.chapter_id == novel_permission_scenario.chapters["restricted"].chapter_id)
        q = chapter_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_guest_cannot_see_chapter_on_private_novel(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(Chapter).where(Chapter.chapter_id == novel_permission_scenario.chapters["private"].chapter_id)
        q = chapter_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_contributor_sees_chapter_on_restricted_novel(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(Chapter).where(Chapter.chapter_id == novel_permission_scenario.chapters["restricted"].chapter_id)
        q = chapter_mod_access_select(q, novel_permission_scenario.users["owner"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_non_contributor_cannot_see_chapter_on_private_novel(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(Chapter).where(Chapter.chapter_id == novel_permission_scenario.chapters["private"].chapter_id)
        q = chapter_mod_access_select(q, novel_permission_scenario.users["other"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_admin_sees_chapter_on_private_novel(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(Chapter).where(Chapter.chapter_id == novel_permission_scenario.chapters["private"].chapter_id)
        q = chapter_mod_access_select(q, novel_permission_scenario.users["admin"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_edit_only_allows_novel_editor(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        chapter_id = novel_permission_scenario.contents["owner_editor_v1"].chapter_id
        q = chapter_mod_access_select(
            select(Chapter).where(Chapter.chapter_id == chapter_id),
            novel_permission_scenario.users["other"],
            edit_only=True,
        )

        assert test_db.execute(q).scalar_one_or_none() is not None

    def test_edit_only_denies_novel_viewer(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        chapter_id = novel_permission_scenario.contents["owner_viewer_v1"].chapter_id
        q = chapter_mod_access_select(
            select(Chapter).where(Chapter.chapter_id == chapter_id),
            novel_permission_scenario.users["other"],
            edit_only=True,
        )

        assert test_db.execute(q).scalar_one_or_none() is None


# ============================================================
# chapter_mod_access_insert
# ============================================================


class TestChapterModAccessInsert:
    def test_owner_can_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_mod_access_insert(
            q, novel_permission_scenario.users["owner"], novel_permission_scenario.novels["rt"].novel_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_editor_can_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_mod_access_insert(
            q, novel_permission_scenario.users["other"], novel_permission_scenario.novels["oe"].novel_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_mod_access_insert(
            q, novel_permission_scenario.users["other"], novel_permission_scenario.novels["ov"].novel_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_non_contributor_cannot_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_mod_access_insert(
            q, novel_permission_scenario.users["other"], novel_permission_scenario.novels["prt"].novel_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_admin_can_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_mod_access_insert(
            q, novel_permission_scenario.users["admin"], novel_permission_scenario.novels["prt"].novel_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None


# ============================================================
# chapter_mod_access_update
# ============================================================


class TestChapterModAccessUpdate:
    def test_owner_can_update(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == novel_permission_scenario.chapters["restricted"].chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, novel_permission_scenario.users["owner"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_editor_can_update(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == novel_permission_scenario.chapters["owner_editor"].chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, novel_permission_scenario.users["other"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_update(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == novel_permission_scenario.chapters["owner_viewer"].chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, novel_permission_scenario.users["other"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    def test_non_contributor_cannot_update(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == novel_permission_scenario.chapters["private"].chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, novel_permission_scenario.users["other"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    def test_admin_can_update_any(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == novel_permission_scenario.chapters["private"].chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, novel_permission_scenario.users["admin"])
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_owner_can_update_aliased_chapter(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        chapter_alias = aliased(Chapter)
        stmt = (
            update(chapter_alias)
            .where(chapter_alias.chapter_id == novel_permission_scenario.chapters["restricted"].chapter_id)
            .values(chapter_title="Aliased Chapter")
            .returning(chapter_alias.chapter_id)
        )
        stmt = chapter_mod_access_update(stmt, novel_permission_scenario.users["owner"], chapter_alias)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result == novel_permission_scenario.chapters["restricted"].chapter_id


# ============================================================
# chapter_content_mod_access_select
# ============================================================


class TestChapterContentModAccessSelect:
    def test_guest_sees_content_on_public_novel(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == novel_permission_scenario.contents["public_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_guest_cannot_see_content_on_restricted_novel(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == novel_permission_scenario.contents["restricted_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_guest_cannot_see_content_on_private_novel(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == novel_permission_scenario.contents["private_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_contributor_sees_content_on_restricted_novel(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == novel_permission_scenario.contents["restricted_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, novel_permission_scenario.users["owner"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_contributor_sees_content_on_private_novel(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == novel_permission_scenario.contents["private_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, novel_permission_scenario.users["owner"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_non_contributor_cannot_see_content_on_private_novel(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == novel_permission_scenario.contents["private_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, novel_permission_scenario.users["other"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_admin_sees_everything(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id.in_(
                [
                    novel_permission_scenario.contents["private_v1"].chapter_content_id,
                    novel_permission_scenario.contents["restricted_v1"].chapter_content_id,
                ]
            )
        )
        q = chapter_content_mod_access_select(q, novel_permission_scenario.users["admin"])
        results = test_db.execute(q).scalars().all()
        assert len(results) == 2

    def test_editor_sees_content_on_shared_novel(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id
            == novel_permission_scenario.contents["owner_editor_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, novel_permission_scenario.users["other"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_sees_content_on_shared_novel(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        """Viewer is a contributor, so can see chapter content."""
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id
            == novel_permission_scenario.contents["owner_viewer_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, novel_permission_scenario.users["other"])
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_edit_only_allows_novel_editor(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        content = novel_permission_scenario.contents["owner_editor_v1"]
        q = chapter_content_mod_access_select(
            select(ChapterContent).where(ChapterContent.chapter_content_id == content.chapter_content_id),
            novel_permission_scenario.users["other"],
            edit_only=True,
        )

        assert test_db.execute(q).scalar_one_or_none() is not None

    def test_edit_only_denies_novel_viewer(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        content = novel_permission_scenario.contents["owner_viewer_v1"]
        q = chapter_content_mod_access_select(
            select(ChapterContent).where(ChapterContent.chapter_content_id == content.chapter_content_id),
            novel_permission_scenario.users["other"],
            edit_only=True,
        )

        assert test_db.execute(q).scalar_one_or_none() is None

    def test_contributor_sees_aliased_content(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        content_alias = aliased(ChapterContent)
        q = select(content_alias).where(
            content_alias.chapter_content_id == novel_permission_scenario.contents["private_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, novel_permission_scenario.users["owner"], content_alias)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_non_contributor_cannot_see_aliased_content(
        self, test_db: Session, novel_permission_scenario: DatabaseScenario
    ):
        content_alias = aliased(ChapterContent)
        q = select(content_alias).where(
            content_alias.chapter_content_id == novel_permission_scenario.contents["private_v1"].chapter_content_id
        )
        q = chapter_content_mod_access_select(q, novel_permission_scenario.users["other"], content_alias)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None


# ============================================================
# chapter_content_mod_access_insert
# ============================================================


class TestChapterContentModAccessInsert:
    def test_owner_can_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_content_mod_access_insert(
            q, novel_permission_scenario.users["owner"], novel_permission_scenario.chapters["restricted"].chapter_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_editor_can_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_content_mod_access_insert(
            q, novel_permission_scenario.users["other"], novel_permission_scenario.chapters["owner_editor"].chapter_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_content_mod_access_insert(
            q, novel_permission_scenario.users["other"], novel_permission_scenario.chapters["owner_viewer"].chapter_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_non_contributor_cannot_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_content_mod_access_insert(
            q, novel_permission_scenario.users["other"], novel_permission_scenario.chapters["private"].chapter_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_admin_can_insert(self, test_db: Session, novel_permission_scenario: DatabaseScenario):
        q = select(1)
        q = chapter_content_mod_access_insert(
            q, novel_permission_scenario.users["admin"], novel_permission_scenario.chapters["private"].chapter_id
        )
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None
