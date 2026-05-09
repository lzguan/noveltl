"""
Tests for novel permission functions in novels/permissions.py.

Tests the permission helpers directly by applying them to raw SQLAlchemy
statements and verifying which rows are returned/affected for each user role.
"""

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.auth.models import User
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
from tests.gate_logging import log_gate

pytestmark = pytest.mark.dependency(
    depends=["gate::fixture_validation"],
    scope="session",
)


# ============================================================
# novel_mod_access_select
# ============================================================


class TestNovelModAccessSelect:
    @pytest.mark.dependency(name="novels::permissions::guest_sees_public_and_unlisted", scope="session")
    def test_guest_sees_public_and_unlisted(
        self,
        test_db: Session,
        p1_novel_public_tyrone: Novel,
        p1_novel_unlisted_tyrone: Novel,
        p1_novel_restricted_tyrone: Novel,
        p1_novel_private_tyrone: Novel,
    ):
        q = select(Novel)
        q = novel_mod_access_select(q, None)
        results = test_db.execute(q).scalars().all()
        ids = {n.novel_id for n in results}
        assert p1_novel_public_tyrone.novel_id in ids
        assert p1_novel_unlisted_tyrone.novel_id in ids
        assert p1_novel_restricted_tyrone.novel_id not in ids
        assert p1_novel_private_tyrone.novel_id not in ids

    @pytest.mark.dependency(name="novels::permissions::non_contributor_sees_public_and_unlisted", scope="session")
    def test_non_contributor_sees_public_and_unlisted(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_novel_public_tyrone: Novel,
        p1_novel_restricted_tyrone: Novel,
        p1_novel_private_tyrone: Novel,
    ):
        q = select(Novel).where(
            Novel.novel_id.in_(
                [
                    p1_novel_public_tyrone.novel_id,
                    p1_novel_restricted_tyrone.novel_id,
                    p1_novel_private_tyrone.novel_id,
                ]
            )
        )
        q = novel_mod_access_select(q, p1_user_2)
        results = test_db.execute(q).scalars().all()
        ids = {n.novel_id for n in results}
        assert p1_novel_public_tyrone.novel_id in ids
        assert p1_novel_restricted_tyrone.novel_id not in ids
        assert p1_novel_private_tyrone.novel_id not in ids

    @pytest.mark.dependency(name="novels::permissions::contributor_sees_own_restricted", scope="session")
    def test_contributor_sees_own_restricted(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_novel_restricted_tyrone: Novel,
    ):
        q = select(Novel).where(Novel.novel_id == p1_novel_restricted_tyrone.novel_id)
        q = novel_mod_access_select(q, p1_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::contributor_sees_own_private", scope="session")
    def test_contributor_sees_own_private(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_novel_private_tyrone: Novel,
    ):
        q = select(Novel).where(Novel.novel_id == p1_novel_private_tyrone.novel_id)
        q = novel_mod_access_select(q, p1_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::admin_sees_everything", scope="session")
    def test_admin_sees_everything(
        self,
        test_db: Session,
        p1_admin: User,
        p1_novel_private_tyrone: Novel,
        p1_novel_restricted_tyrone: Novel,
    ):
        q = select(Novel).where(
            Novel.novel_id.in_(
                [
                    p1_novel_private_tyrone.novel_id,
                    p1_novel_restricted_tyrone.novel_id,
                ]
            )
        )
        q = novel_mod_access_select(q, p1_admin)
        results = test_db.execute(q).scalars().all()
        assert len(results) == 2

    @pytest.mark.dependency(name="novels::permissions::editor_sees_private_novel", scope="session")
    def test_editor_sees_private_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_novel_owner_editor: Novel,
    ):
        q = select(Novel).where(Novel.novel_id == p1_novel_owner_editor.novel_id)
        q = novel_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::viewer_sees_private_novel", scope="session")
    def test_viewer_sees_private_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_novel_owner_viewer: Novel,
    ):
        q = select(Novel).where(Novel.novel_id == p1_novel_owner_viewer.novel_id)
        q = novel_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(
        name="gate::novels::permissions::novel_mod_access_select",
        depends=[
            "novels::permissions::guest_sees_public_and_unlisted",
            "novels::permissions::non_contributor_sees_public_and_unlisted",
            "novels::permissions::contributor_sees_own_restricted",
            "novels::permissions::contributor_sees_own_private",
            "novels::permissions::admin_sees_everything",
            "novels::permissions::editor_sees_private_novel",
            "novels::permissions::viewer_sees_private_novel",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# ============================================================
# novel_mod_access_update
# ============================================================


class TestNovelModAccessUpdate:
    @pytest.mark.dependency(name="novels::permissions::owner_can_update", scope="session")
    def test_owner_can_update(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_novel_public_tyrone: Novel,
    ):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == p1_novel_public_tyrone.novel_id)
            .values(novel_description="updated")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, p1_user_1)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::editor_can_update", scope="session")
    def test_editor_can_update(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_novel_owner_editor: Novel,
    ):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == p1_novel_owner_editor.novel_id)
            .values(novel_description="editor update")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, p1_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::viewer_cannot_update", scope="session")
    def test_viewer_cannot_update(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_novel_owner_viewer: Novel,
    ):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == p1_novel_owner_viewer.novel_id)
            .values(novel_description="viewer update")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, p1_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::non_contributor_cannot_update", scope="session")
    def test_non_contributor_cannot_update(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_novel_public_tyrone: Novel,
    ):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == p1_novel_public_tyrone.novel_id)
            .values(novel_description="hacked")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, p1_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::admin_can_update_any", scope="session")
    def test_admin_can_update_any(
        self,
        test_db: Session,
        p1_admin: User,
        p1_novel_private_tyrone: Novel,
    ):
        stmt = (
            update(Novel)
            .where(Novel.novel_id == p1_novel_private_tyrone.novel_id)
            .values(novel_description="admin")
            .returning(Novel)
        )
        stmt = novel_mod_access_update(stmt, p1_admin)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(
        name="gate::novels::permissions::novel_mod_access_update",
        depends=[
            "novels::permissions::owner_can_update",
            "novels::permissions::editor_can_update",
            "novels::permissions::viewer_cannot_update",
            "novels::permissions::non_contributor_cannot_update",
            "novels::permissions::admin_can_update_any",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# ============================================================
# chapter_mod_access_select
# ============================================================


class TestChapterModAccessSelect:
    @pytest.mark.dependency(name="novels::permissions::guest_sees_chapter_on_public_novel", scope="session")
    def test_guest_sees_chapter_on_public_novel(
        self,
        test_db: Session,
        p1_chapter_public: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_public.chapter_id)
        q = chapter_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::guest_cannot_see_chapter_on_restricted_novel", scope="session")
    def test_guest_cannot_see_chapter_on_restricted_novel(
        self,
        test_db: Session,
        p1_chapter_restricted: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_restricted.chapter_id)
        q = chapter_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::guest_cannot_see_chapter_on_private_novel", scope="session")
    def test_guest_cannot_see_chapter_on_private_novel(
        self,
        test_db: Session,
        p1_chapter_private: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_private.chapter_id)
        q = chapter_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::contributor_sees_chapter_on_restricted_novel", scope="session")
    def test_contributor_sees_chapter_on_restricted_novel(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_chapter_restricted: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_restricted.chapter_id)
        q = chapter_mod_access_select(q, p1_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(
        name="novels::permissions::non_contributor_cannot_see_chapter_on_private_novel", scope="session"
    )
    def test_non_contributor_cannot_see_chapter_on_private_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_private: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_private.chapter_id)
        q = chapter_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::admin_sees_chapter_on_private_novel", scope="session")
    def test_admin_sees_chapter_on_private_novel(
        self,
        test_db: Session,
        p1_admin: User,
        p1_chapter_private: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_private.chapter_id)
        q = chapter_mod_access_select(q, p1_admin)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(
        name="gate::novels::permissions::chapter_mod_access_select",
        depends=[
            "novels::permissions::guest_sees_chapter_on_public_novel",
            "novels::permissions::guest_cannot_see_chapter_on_restricted_novel",
            "novels::permissions::guest_cannot_see_chapter_on_private_novel",
            "novels::permissions::contributor_sees_chapter_on_restricted_novel",
            "novels::permissions::non_contributor_cannot_see_chapter_on_private_novel",
            "novels::permissions::admin_sees_chapter_on_private_novel",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# ============================================================
# chapter_mod_access_insert
# ============================================================


class TestChapterModAccessInsert:
    @pytest.mark.dependency(name="novels::permissions::owner_can_insert_chapter", scope="session")
    def test_owner_can_insert(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_novel_restricted_tyrone: Novel,
    ):
        q = select(1)
        q = chapter_mod_access_insert(q, p1_user_1, p1_novel_restricted_tyrone.novel_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::editor_can_insert_chapter", scope="session")
    def test_editor_can_insert(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_novel_owner_editor: Novel,
    ):
        q = select(1)
        q = chapter_mod_access_insert(q, p1_user_2, p1_novel_owner_editor.novel_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::viewer_cannot_insert_chapter", scope="session")
    def test_viewer_cannot_insert(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_novel_owner_viewer: Novel,
    ):
        q = select(1)
        q = chapter_mod_access_insert(q, p1_user_2, p1_novel_owner_viewer.novel_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::non_contributor_cannot_insert_chapter", scope="session")
    def test_non_contributor_cannot_insert(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_novel_private_tyrone: Novel,
    ):
        q = select(1)
        q = chapter_mod_access_insert(q, p1_user_2, p1_novel_private_tyrone.novel_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::admin_can_insert_chapter", scope="session")
    def test_admin_can_insert(
        self,
        test_db: Session,
        p1_admin: User,
        p1_novel_private_tyrone: Novel,
    ):
        q = select(1)
        q = chapter_mod_access_insert(q, p1_admin, p1_novel_private_tyrone.novel_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(
        name="gate::novels::permissions::chapter_mod_access_insert",
        depends=[
            "novels::permissions::owner_can_insert_chapter",
            "novels::permissions::editor_can_insert_chapter",
            "novels::permissions::viewer_cannot_insert_chapter",
            "novels::permissions::non_contributor_cannot_insert_chapter",
            "novels::permissions::admin_can_insert_chapter",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# ============================================================
# chapter_mod_access_update
# ============================================================


class TestChapterModAccessUpdate:
    @pytest.mark.dependency(name="novels::permissions::owner_can_update_chapter", scope="session")
    def test_owner_can_update(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_chapter_restricted: Chapter,
    ):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == p1_chapter_restricted.chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, p1_user_1)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::editor_can_update_chapter", scope="session")
    def test_editor_can_update(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_owner_editor: Chapter,
    ):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == p1_chapter_owner_editor.chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, p1_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::viewer_cannot_update_chapter", scope="session")
    def test_viewer_cannot_update(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_owner_viewer: Chapter,
    ):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == p1_chapter_owner_viewer.chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, p1_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::non_contributor_cannot_update_chapter", scope="session")
    def test_non_contributor_cannot_update(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_private: Chapter,
    ):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == p1_chapter_private.chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, p1_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::admin_can_update_any_chapter", scope="session")
    def test_admin_can_update_any(
        self,
        test_db: Session,
        p1_admin: User,
        p1_chapter_private: Chapter,
    ):
        stmt = (
            update(Chapter)
            .where(Chapter.chapter_id == p1_chapter_private.chapter_id)
            .values(chapter_num=99)
            .returning(Chapter)
        )
        stmt = chapter_mod_access_update(stmt, p1_admin)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(
        name="gate::novels::permissions::chapter_mod_access_update",
        depends=[
            "novels::permissions::owner_can_update_chapter",
            "novels::permissions::editor_can_update_chapter",
            "novels::permissions::viewer_cannot_update_chapter",
            "novels::permissions::non_contributor_cannot_update_chapter",
            "novels::permissions::admin_can_update_any_chapter",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# ============================================================
# chapter_content_mod_access_select
# ============================================================


class TestChapterContentModAccessSelect:
    @pytest.mark.dependency(name="novels::permissions::guest_sees_content_on_public_novel", scope="session")
    def test_guest_sees_content_on_public_novel(
        self,
        test_db: Session,
        p1_chapter_content_public: ChapterContent,
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == p1_chapter_content_public.chapter_content_id
        )
        q = chapter_content_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::guest_cannot_see_content_on_restricted_novel", scope="session")
    def test_guest_cannot_see_content_on_restricted_novel(
        self,
        test_db: Session,
        p1_chapter_content_restricted: ChapterContent,
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == p1_chapter_content_restricted.chapter_content_id
        )
        q = chapter_content_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::guest_cannot_see_content_on_private_novel", scope="session")
    def test_guest_cannot_see_content_on_private_novel(
        self,
        test_db: Session,
        p1_chapter_content_private: ChapterContent,
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == p1_chapter_content_private.chapter_content_id
        )
        q = chapter_content_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::contributor_sees_content_on_restricted_novel", scope="session")
    def test_contributor_sees_content_on_restricted_novel(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_chapter_content_restricted: ChapterContent,
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == p1_chapter_content_restricted.chapter_content_id
        )
        q = chapter_content_mod_access_select(q, p1_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::contributor_sees_content_on_private_novel", scope="session")
    def test_contributor_sees_content_on_private_novel(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_chapter_content_private: ChapterContent,
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == p1_chapter_content_private.chapter_content_id
        )
        q = chapter_content_mod_access_select(q, p1_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(
        name="novels::permissions::non_contributor_cannot_see_content_on_private_novel", scope="session"
    )
    def test_non_contributor_cannot_see_content_on_private_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_content_private: ChapterContent,
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == p1_chapter_content_private.chapter_content_id
        )
        q = chapter_content_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::admin_sees_all_content", scope="session")
    def test_admin_sees_everything(
        self,
        test_db: Session,
        p1_admin: User,
        p1_chapter_content_private: ChapterContent,
        p1_chapter_content_restricted: ChapterContent,
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id.in_(
                [
                    p1_chapter_content_private.chapter_content_id,
                    p1_chapter_content_restricted.chapter_content_id,
                ]
            )
        )
        q = chapter_content_mod_access_select(q, p1_admin)
        results = test_db.execute(q).scalars().all()
        assert len(results) == 2

    @pytest.mark.dependency(name="novels::permissions::editor_sees_content_on_shared_novel", scope="session")
    def test_editor_sees_content_on_shared_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_content_owner_editor: ChapterContent,
    ):
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == p1_chapter_content_owner_editor.chapter_content_id
        )
        q = chapter_content_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::viewer_sees_content_on_shared_novel", scope="session")
    def test_viewer_sees_content_on_shared_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_content_owner_viewer: ChapterContent,
    ):
        """Viewer is a contributor, so can see chapter content."""
        q = select(ChapterContent).where(
            ChapterContent.chapter_content_id == p1_chapter_content_owner_viewer.chapter_content_id
        )
        q = chapter_content_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(
        name="gate::novels::permissions::chapter_content_mod_access_select",
        depends=[
            "novels::permissions::guest_sees_content_on_public_novel",
            "novels::permissions::guest_cannot_see_content_on_restricted_novel",
            "novels::permissions::guest_cannot_see_content_on_private_novel",
            "novels::permissions::contributor_sees_content_on_restricted_novel",
            "novels::permissions::contributor_sees_content_on_private_novel",
            "novels::permissions::non_contributor_cannot_see_content_on_private_novel",
            "novels::permissions::admin_sees_all_content",
            "novels::permissions::editor_sees_content_on_shared_novel",
            "novels::permissions::viewer_sees_content_on_shared_novel",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


# ============================================================
# chapter_content_mod_access_insert
# ============================================================


class TestChapterContentModAccessInsert:
    @pytest.mark.dependency(name="novels::permissions::owner_can_insert_content", scope="session")
    def test_owner_can_insert(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_chapter_restricted: Chapter,
    ):
        q = select(1)
        q = chapter_content_mod_access_insert(q, p1_user_1, p1_chapter_restricted.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::editor_can_insert_content", scope="session")
    def test_editor_can_insert(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_owner_editor: Chapter,
    ):
        q = select(1)
        q = chapter_content_mod_access_insert(q, p1_user_2, p1_chapter_owner_editor.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(name="novels::permissions::viewer_cannot_insert_content", scope="session")
    def test_viewer_cannot_insert(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_owner_viewer: Chapter,
    ):
        q = select(1)
        q = chapter_content_mod_access_insert(q, p1_user_2, p1_chapter_owner_viewer.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::non_contributor_cannot_insert_content", scope="session")
    def test_non_contributor_cannot_insert(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_private: Chapter,
    ):
        q = select(1)
        q = chapter_content_mod_access_insert(q, p1_user_2, p1_chapter_private.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    @pytest.mark.dependency(name="novels::permissions::admin_can_insert_content", scope="session")
    def test_admin_can_insert(
        self,
        test_db: Session,
        p1_admin: User,
        p1_chapter_private: Chapter,
    ):
        q = select(1)
        q = chapter_content_mod_access_insert(q, p1_admin, p1_chapter_private.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    @pytest.mark.dependency(
        name="gate::novels::permissions::chapter_content_mod_access_insert",
        depends=[
            "novels::permissions::owner_can_insert_content",
            "novels::permissions::editor_can_insert_content",
            "novels::permissions::viewer_cannot_insert_content",
            "novels::permissions::non_contributor_cannot_insert_content",
            "novels::permissions::admin_can_insert_content",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::novels::permissions",
    depends=[
        "gate::novels::permissions::novel_mod_access_select",
        "gate::novels::permissions::novel_mod_access_update",
        "gate::novels::permissions::chapter_mod_access_select",
        "gate::novels::permissions::chapter_mod_access_insert",
        "gate::novels::permissions::chapter_mod_access_update",
        "gate::novels::permissions::chapter_content_mod_access_select",
        "gate::novels::permissions::chapter_content_mod_access_insert",
    ],
    scope="session",
)
def test_gate():
    """All novels permissions tests must pass before downstream layers run."""
    log_gate("gate::novels::permissions")
