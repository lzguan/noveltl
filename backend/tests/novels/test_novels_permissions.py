"""
Tests for novel permission functions in novels/permissions.py.

Tests the permission helpers directly by applying them to raw SQLAlchemy
statements and verifying which rows are returned/affected for each user role.
"""

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from src.auth.models import User
from src.novels.models import Chapter, Novel, Revision, RevisionText
from src.novels.permissions import (
    chapter_mod_access_insert,
    chapter_mod_access_select,
    chapter_mod_access_update,
    novel_mod_access_select,
    novel_mod_access_update,
    revision_mod_access_delete,
    revision_mod_access_insert,
    revision_mod_access_select,
    revision_mod_access_update,
)

# ============================================================
# novel_mod_access_select
# ============================================================


class TestNovelModAccessSelect:
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


# ============================================================
# novel_mod_access_update
# ============================================================


class TestNovelModAccessUpdate:
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


# ============================================================
# chapter_mod_access_select
# ============================================================


class TestChapterModAccessSelect:
    def test_guest_sees_chapter_on_public_novel(
        self,
        test_db: Session,
        p1_chapter_public: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_public.chapter_id)
        q = q.join(Novel, Chapter.novel_id == Novel.novel_id)
        q = chapter_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_guest_cannot_see_chapter_on_restricted_novel(
        self,
        test_db: Session,
        p1_chapter_restricted: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_restricted.chapter_id)
        q = q.join(Novel, Chapter.novel_id == Novel.novel_id)
        q = chapter_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_guest_cannot_see_chapter_on_private_novel(
        self,
        test_db: Session,
        p1_chapter_private: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_private.chapter_id)
        q = q.join(Novel, Chapter.novel_id == Novel.novel_id)
        q = chapter_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_contributor_sees_chapter_on_restricted_novel(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_chapter_restricted: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_restricted.chapter_id)
        q = q.join(Novel, Chapter.novel_id == Novel.novel_id)
        q = chapter_mod_access_select(q, p1_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_non_contributor_cannot_see_chapter_on_private_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_private: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_private.chapter_id)
        q = q.join(Novel, Chapter.novel_id == Novel.novel_id)
        q = chapter_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_admin_sees_chapter_on_private_novel(
        self,
        test_db: Session,
        p1_admin: User,
        p1_chapter_private: Chapter,
    ):
        q = select(Chapter).where(Chapter.chapter_id == p1_chapter_private.chapter_id)
        q = q.join(Novel, Chapter.novel_id == Novel.novel_id)
        q = chapter_mod_access_select(q, p1_admin)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None


# ============================================================
# chapter_mod_access_insert
# ============================================================


class TestChapterModAccessInsert:
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


# ============================================================
# chapter_mod_access_update
# ============================================================


class TestChapterModAccessUpdate:
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


# ============================================================
# revision_mod_access_select
# ============================================================


class TestRevisionModAccessSelect:
    def test_guest_sees_public_revision_on_public_novel(
        self,
        test_db: Session,
        p1_revision_public: tuple[Revision, RevisionText],
    ):
        q = select(Revision).where(Revision.revision_id == p1_revision_public[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_guest_cannot_see_draft_on_public_novel(
        self,
        test_db: Session,
        p1_revision_draft_on_public: tuple[Revision, RevisionText],
    ):
        q = select(Revision).where(Revision.revision_id == p1_revision_draft_on_public[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_guest_cannot_see_public_revision_on_restricted_novel(
        self,
        test_db: Session,
        p1_revision_restricted: tuple[Revision, RevisionText],
    ):
        q = select(Revision).where(Revision.revision_id == p1_revision_restricted[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, None)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_non_contributor_cannot_see_draft_on_public_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_draft_on_public: tuple[Revision, RevisionText],
    ):
        """Non-contributor can see public revisions on public novels, but not drafts."""
        q = select(Revision).where(Revision.revision_id == p1_revision_draft_on_public[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_non_contributor_sees_public_revision_on_public_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_public: tuple[Revision, RevisionText],
    ):
        q = select(Revision).where(Revision.revision_id == p1_revision_public[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_contributor_sees_draft_on_own_novel(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_revision_draft_on_public: tuple[Revision, RevisionText],
    ):
        """Owner can see non-public revisions on their own novel."""
        q = select(Revision).where(Revision.revision_id == p1_revision_draft_on_public[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, p1_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_contributor_sees_revision_on_restricted_novel(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_revision_restricted: tuple[Revision, RevisionText],
    ):
        q = select(Revision).where(Revision.revision_id == p1_revision_restricted[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, p1_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_contributor_sees_revision_on_private_novel(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_revision_private: tuple[Revision, RevisionText],
    ):
        q = select(Revision).where(Revision.revision_id == p1_revision_private[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, p1_user_1)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_non_contributor_cannot_see_revision_on_private_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_private: tuple[Revision, RevisionText],
    ):
        q = select(Revision).where(Revision.revision_id == p1_revision_private[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_admin_sees_everything(
        self,
        test_db: Session,
        p1_admin: User,
        p1_revision_private: tuple[Revision, RevisionText],
        p1_revision_draft_on_public: tuple[Revision, RevisionText],
    ):
        q = select(Revision).where(
            Revision.revision_id.in_(
                [
                    p1_revision_private[0].revision_id,
                    p1_revision_draft_on_public[0].revision_id,
                ]
            )
        )
        q = revision_mod_access_select(q, p1_admin)
        results = test_db.execute(q).scalars().all()
        assert len(results) == 2

    def test_editor_sees_draft_on_shared_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_owner_editor: tuple[Revision, RevisionText],
    ):
        q = select(Revision).where(Revision.revision_id == p1_revision_owner_editor[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_sees_draft_on_shared_novel(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_owner_viewer: tuple[Revision, RevisionText],
    ):
        """Viewer is a contributor, so can see non-public revisions."""
        q = select(Revision).where(Revision.revision_id == p1_revision_owner_viewer[0].revision_id)
        q = q.join(Chapter, Chapter.chapter_id == Revision.chapter_id)
        q = q.join(Novel, Novel.novel_id == Chapter.novel_id)
        q = revision_mod_access_select(q, p1_user_2)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None


# ============================================================
# revision_mod_access_insert
# ============================================================


class TestRevisionModAccessInsert:
    def test_owner_can_insert(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_chapter_restricted: Chapter,
    ):
        q = select(1)
        q = revision_mod_access_insert(q, p1_user_1, p1_chapter_restricted.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_editor_can_insert(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_owner_editor: Chapter,
    ):
        q = select(1)
        q = revision_mod_access_insert(q, p1_user_2, p1_chapter_owner_editor.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_insert(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_owner_viewer: Chapter,
    ):
        q = select(1)
        q = revision_mod_access_insert(q, p1_user_2, p1_chapter_owner_viewer.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_non_contributor_cannot_insert(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_chapter_private: Chapter,
    ):
        q = select(1)
        q = revision_mod_access_insert(q, p1_user_2, p1_chapter_private.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is None

    def test_admin_can_insert(
        self,
        test_db: Session,
        p1_admin: User,
        p1_chapter_private: Chapter,
    ):
        q = select(1)
        q = revision_mod_access_insert(q, p1_admin, p1_chapter_private.chapter_id)
        result = test_db.execute(q).scalar_one_or_none()
        assert result is not None


# ============================================================
# revision_mod_access_update
# ============================================================


class TestRevisionModAccessUpdate:
    def test_owner_can_update(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_revision_restricted: tuple[Revision, RevisionText],
    ):
        stmt = (
            update(Revision)
            .where(Revision.revision_id == p1_revision_restricted[0].revision_id)
            .values(revision_title="Updated")
            .returning(Revision)
        )
        stmt = revision_mod_access_update(stmt, p1_user_1)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_editor_can_update(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_owner_editor: tuple[Revision, RevisionText],
    ):
        stmt = (
            update(Revision)
            .where(Revision.revision_id == p1_revision_owner_editor[0].revision_id)
            .values(revision_title="Editor Updated")
            .returning(Revision)
        )
        stmt = revision_mod_access_update(stmt, p1_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None

    def test_viewer_cannot_update(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_owner_viewer: tuple[Revision, RevisionText],
    ):
        stmt = (
            update(Revision)
            .where(Revision.revision_id == p1_revision_owner_viewer[0].revision_id)
            .values(revision_title="Viewer Updated")
            .returning(Revision)
        )
        stmt = revision_mod_access_update(stmt, p1_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    def test_non_contributor_cannot_update(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_private: tuple[Revision, RevisionText],
    ):
        stmt = (
            update(Revision)
            .where(Revision.revision_id == p1_revision_private[0].revision_id)
            .values(revision_title="Hacked")
            .returning(Revision)
        )
        stmt = revision_mod_access_update(stmt, p1_user_2)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is None

    def test_admin_can_update_any(
        self,
        test_db: Session,
        p1_admin: User,
        p1_revision_private: tuple[Revision, RevisionText],
    ):
        stmt = (
            update(Revision)
            .where(Revision.revision_id == p1_revision_private[0].revision_id)
            .values(revision_title="Admin")
            .returning(Revision)
        )
        stmt = revision_mod_access_update(stmt, p1_admin)
        result = test_db.execute(stmt).scalar_one_or_none()
        assert result is not None


# ============================================================
# revision_mod_access_delete
# ============================================================


class TestRevisionModAccessDelete:
    def test_owner_can_delete(
        self,
        test_db: Session,
        p1_user_1: User,
        p1_revision_restricted: tuple[Revision, RevisionText],
    ):
        stmt = delete(Revision).where(Revision.revision_id == p1_revision_restricted[0].revision_id)
        stmt = revision_mod_access_delete(stmt, p1_user_1)
        test_db.execute(stmt)
        test_db.commit()
        remaining = test_db.execute(
            select(Revision).where(Revision.revision_id == p1_revision_restricted[0].revision_id)
        ).scalar_one_or_none()
        assert remaining is None

    def test_editor_cannot_delete(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_owner_editor: tuple[Revision, RevisionText],
    ):
        """Delete requires OWNER role, not EDITOR."""
        stmt = delete(Revision).where(Revision.revision_id == p1_revision_owner_editor[0].revision_id)
        stmt = revision_mod_access_delete(stmt, p1_user_2)
        test_db.execute(stmt)
        test_db.commit()
        remaining = test_db.execute(
            select(Revision).where(Revision.revision_id == p1_revision_owner_editor[0].revision_id)
        ).scalar_one_or_none()
        assert remaining is not None

    def test_viewer_cannot_delete(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_owner_viewer: tuple[Revision, RevisionText],
    ):
        stmt = delete(Revision).where(Revision.revision_id == p1_revision_owner_viewer[0].revision_id)
        stmt = revision_mod_access_delete(stmt, p1_user_2)
        test_db.execute(stmt)
        test_db.commit()
        remaining = test_db.execute(
            select(Revision).where(Revision.revision_id == p1_revision_owner_viewer[0].revision_id)
        ).scalar_one_or_none()
        assert remaining is not None

    def test_non_contributor_cannot_delete(
        self,
        test_db: Session,
        p1_user_2: User,
        p1_revision_private: tuple[Revision, RevisionText],
    ):
        stmt = delete(Revision).where(Revision.revision_id == p1_revision_private[0].revision_id)
        stmt = revision_mod_access_delete(stmt, p1_user_2)
        test_db.execute(stmt)
        test_db.commit()
        remaining = test_db.execute(
            select(Revision).where(Revision.revision_id == p1_revision_private[0].revision_id)
        ).scalar_one_or_none()
        assert remaining is not None

    def test_admin_can_delete_any(
        self,
        test_db: Session,
        p1_admin: User,
        p1_revision_private: tuple[Revision, RevisionText],
    ):
        stmt = delete(Revision).where(Revision.revision_id == p1_revision_private[0].revision_id)
        stmt = revision_mod_access_delete(stmt, p1_admin)
        test_db.execute(stmt)
        test_db.commit()
        remaining = test_db.execute(
            select(Revision).where(Revision.revision_id == p1_revision_private[0].revision_id)
        ).scalar_one_or_none()
        assert remaining is None
