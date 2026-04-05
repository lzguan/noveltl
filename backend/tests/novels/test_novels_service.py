"""
Service-level permission tests for novels and chapters.

Tests query_novels_by_title, query_novel_by_id, query_chapters_by_novel,
query_chapter_by_id, query_chapter_content_by_most_recent, and
insert_chapter permission behavior.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.exceptions import InsufficientPermissionsException
from src.novels import schemas
from src.novels.constants import NovelType, Visibility
from src.novels.exceptions import (
    ChapterNotFoundException,
    NovelNotFoundException,
)
from src.novels.models import ChapterContent, Novel
from src.novels.service import (
    insert_chapter,
    query_chapter_by_id,
    query_chapter_content_by_most_recent,
    query_chapters_by_novel,
    query_novel_by_id,
    query_novels_by_title,
)

pytestmark = pytest.mark.dependency(
    depends=["gate::novels::permissions", "gate::novels::utils"],
    scope="session",
)


class TestQueryNovelsByTitle:
    """Tests for query_novels_by_title service function."""

    @pytest.mark.dependency(name="novels::service::guest_sees_public_novels", scope="session")
    def test_guest_sees_public_novels(
        self, test_db: Session, p1_novels: dict[str, Novel],
    ):
        results = query_novels_by_title(test_db, None, "")
        assert len(results) == 2
        titles = [n.novel_title for n in results]
        assert "pt" in titles
        assert "ps" in titles

    @pytest.mark.dependency(name="novels::service::regular_user_sees_public_novels", scope="session")
    def test_regular_user_sees_public_novels(
        self, test_db: Session, p1_novels: dict[str, Novel], p1_user_1: User,
    ):
        results = query_novels_by_title(test_db, p1_user_1, "")
        assert len(results) == 2
        titles = [n.novel_title for n in results]
        assert "pt" in titles
        assert "ps" in titles

    @pytest.mark.dependency(name="novels::service::other_user_sees_public_novels", scope="session")
    def test_other_user_sees_public_novels(
        self, test_db: Session, p1_novels: dict[str, Novel], p1_user_2: User,
    ):
        results = query_novels_by_title(test_db, p1_user_2, "")
        assert len(results) == 2
        titles = [n.novel_title for n in results]
        assert "pt" in titles
        assert "ps" in titles

    @pytest.mark.dependency(name="novels::service::admin_sees_public_novels", scope="session")
    def test_admin_sees_public_novels(
        self, test_db: Session, p1_novels: dict[str, Novel], p1_admin: User,
    ):
        results = query_novels_by_title(test_db, p1_admin, "")
        assert len(results) == 2
        titles = [n.novel_title for n in results]
        assert "pt" in titles
        assert "ps" in titles

    @pytest.mark.dependency(name="novels::service::search_filters_by_title", scope="session")
    def test_search_filters_by_title(
        self, test_db: Session, p1_novels: dict[str, Novel],
    ):
        results = query_novels_by_title(test_db, None, "t")
        assert len(results) == 1
        assert results[0].novel_title == "pt"

    @pytest.mark.dependency(
        name="gate::novels::service::query_novels_by_title",
        depends=[
            "novels::service::guest_sees_public_novels",
            "novels::service::regular_user_sees_public_novels",
            "novels::service::other_user_sees_public_novels",
            "novels::service::admin_sees_public_novels",
            "novels::service::search_filters_by_title",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestQueryNovelById:
    """Tests for query_novel_by_id service function."""

    @pytest.mark.dependency(name="novels::service::unlisted_novel_visible_to_contributor", scope="session")
    def test_unlisted_novel_visible_to_contributor(
        self, test_db: Session, p1_novels: dict[str, Novel], p1_user_2: User,
    ):
        us = query_novel_by_id(test_db, p1_user_2, p1_novels["us"].novel_id)
        assert us.novel_title == "us"
        assert us.novel_visibility == Visibility.UNLISTED
        assert us.novel_type == NovelType.ORIGINAL

    @pytest.mark.dependency(name="novels::service::unlisted_novel_visible_to_guest", scope="session")
    def test_unlisted_novel_visible_to_guest(
        self, test_db: Session, p1_novels: dict[str, Novel],
    ):
        query_novel_by_id(test_db, None, p1_novels["us"].novel_id)

    @pytest.mark.dependency(name="novels::service::unlisted_novel_visible_to_other_user", scope="session")
    def test_unlisted_novel_visible_to_other_user(
        self, test_db: Session, p1_novels: dict[str, Novel], p1_user_1: User,
    ):
        query_novel_by_id(test_db, p1_user_1, p1_novels["us"].novel_id)

    @pytest.mark.dependency(name="novels::service::restricted_novel_not_visible_to_guest", scope="session")
    def test_restricted_novel_not_visible_to_guest(
        self, test_db: Session, p1_novels: dict[str, Novel],
    ):
        with pytest.raises(NovelNotFoundException):
            query_novel_by_id(test_db, None, p1_novels["rt"].novel_id)

    @pytest.mark.dependency(name="novels::service::restricted_novel_visible_to_contributor", scope="session")
    def test_restricted_novel_visible_to_contributor(
        self, test_db: Session, p1_novels: dict[str, Novel], p1_user_1: User,
    ):
        rt = query_novel_by_id(test_db, p1_user_1, p1_novels["rt"].novel_id)
        assert rt.novel_title == "rt"
        assert rt.novel_visibility == Visibility.RESTRICTED
        assert rt.novel_type == NovelType.ORIGINAL

    @pytest.mark.dependency(name="novels::service::private_novel_not_visible_to_guest", scope="session")
    def test_private_novel_not_visible_to_guest(
        self, test_db: Session, p1_novels: dict[str, Novel],
    ):
        with pytest.raises(NovelNotFoundException):
            query_novel_by_id(test_db, None, p1_novels["prt"].novel_id)

    @pytest.mark.dependency(name="novels::service::private_novel_visible_to_admin", scope="session")
    def test_private_novel_visible_to_admin(
        self, test_db: Session, p1_novels: dict[str, Novel], p1_admin: User,
    ):
        prt = query_novel_by_id(test_db, p1_admin, p1_novels["prt"].novel_id)
        assert prt.novel_title == "prt"
        assert prt.novel_visibility == Visibility.PRIVATE
        assert prt.novel_type == NovelType.ORIGINAL

    @pytest.mark.dependency(name="novels::service::private_novel_visible_to_owner", scope="session")
    def test_private_novel_visible_to_owner(
        self, test_db: Session, p1_novels: dict[str, Novel], p1_user_1: User,
    ):
        oe = query_novel_by_id(test_db, p1_user_1, p1_novels["oe"].novel_id)
        assert oe.novel_title == "oe"
        assert oe.novel_visibility == Visibility.PRIVATE

    @pytest.mark.dependency(name="novels::service::private_novel_visible_to_both_contributors", scope="session")
    def test_private_novel_visible_to_both_contributors(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ):
        oe_u1 = query_novel_by_id(test_db, p1_user_1, p1_novels["oe"].novel_id)
        oe_u2 = query_novel_by_id(test_db, p1_user_2, p1_novels["oe"].novel_id)
        assert oe_u1.novel_title == oe_u2.novel_title

    @pytest.mark.dependency(name="novels::service::private_novel_not_visible_to_non_contributor", scope="session")
    def test_private_novel_not_visible_to_non_contributor(
        self, test_db: Session, p1_novels: dict[str, Novel],
    ):
        with pytest.raises(NovelNotFoundException):
            query_novel_by_id(test_db, None, p1_novels["oe"].novel_id)

    @pytest.mark.dependency(
        name="gate::novels::service::query_novel_by_id",
        depends=[
            "novels::service::unlisted_novel_visible_to_contributor",
            "novels::service::unlisted_novel_visible_to_guest",
            "novels::service::unlisted_novel_visible_to_other_user",
            "novels::service::restricted_novel_not_visible_to_guest",
            "novels::service::restricted_novel_visible_to_contributor",
            "novels::service::private_novel_not_visible_to_guest",
            "novels::service::private_novel_visible_to_admin",
            "novels::service::private_novel_visible_to_owner",
            "novels::service::private_novel_visible_to_both_contributors",
            "novels::service::private_novel_not_visible_to_non_contributor",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestQueryChaptersByNovel:
    """Tests for query_chapters_by_novel service function."""

    @pytest.mark.dependency(name="novels::service::non_contributor_cannot_query_restricted_novel", scope="session")
    def test_non_contributor_cannot_query_restricted_novel(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ):
        rt = p1_novels["rt"]
        for i in range(3):
            insert_chapter(
                test_db, p1_user_1, rt.novel_id, schemas.CreateChapter(chapter_num=i)
            )
        with pytest.raises(NovelNotFoundException):
            query_chapters_by_novel(
                test_db, p1_user_2, rt.novel_id, start=None, end=None
            )

    @pytest.mark.dependency(name="novels::service::admin_can_query_restricted_novel", scope="session")
    def test_admin_can_query_restricted_novel(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_admin: User,
    ):
        rt = p1_novels["rt"]
        for i in range(3):
            insert_chapter(
                test_db, p1_user_1, rt.novel_id, schemas.CreateChapter(chapter_num=i)
            )
        chapters = query_chapters_by_novel(
            test_db, p1_admin, rt.novel_id, start=None, end=None
        )
        assert len(chapters) == 3

    @pytest.mark.dependency(name="novels::service::contributor_can_query_restricted_novel", scope="session")
    def test_contributor_can_query_restricted_novel(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ):
        rt = p1_novels["rt"]
        for i in range(3):
            insert_chapter(
                test_db, p1_user_1, rt.novel_id, schemas.CreateChapter(chapter_num=i)
            )
        chapters = query_chapters_by_novel(
            test_db, p1_user_1, rt.novel_id, start=None, end=None
        )
        assert len(chapters) == 3

    @pytest.mark.dependency(name="novels::service::guest_cannot_query_private_novel", scope="session")
    def test_guest_cannot_query_private_novel(
        self, test_db: Session, p1_novels: dict[str, Novel],
    ):
        oe = p1_novels["oe"]
        with pytest.raises(NovelNotFoundException):
            query_chapters_by_novel(test_db, None, oe.novel_id, start=None, end=None)

    @pytest.mark.dependency(name="novels::service::admin_can_query_private_novel", scope="session")
    def test_admin_can_query_private_novel(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_admin: User,
    ):
        oe = p1_novels["oe"]
        insert_chapter(
            test_db, p1_user_1, oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        chapters = query_chapters_by_novel(
            test_db, p1_admin, oe.novel_id, start=None, end=None
        )
        assert len(chapters) == 1

    @pytest.mark.dependency(name="novels::service::contributor_can_query_viewer_restricted_novel", scope="session")
    def test_contributor_can_query_viewer_restricted_novel(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ):
        ov = p1_novels["ov"]
        insert_chapter(
            test_db, p1_user_1, ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        chapters = query_chapters_by_novel(
            test_db, p1_user_2, ov.novel_id, start=None, end=None
        )
        assert len(chapters) == 1

    @pytest.mark.dependency(name="novels::service::guest_cannot_query_viewer_restricted_novel", scope="session")
    def test_guest_cannot_query_viewer_restricted_novel(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ):
        ov = p1_novels["ov"]
        insert_chapter(
            test_db, p1_user_1, ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(NovelNotFoundException):
            query_chapters_by_novel(test_db, None, ov.novel_id, start=None, end=None)

    @pytest.mark.dependency(
        name="gate::novels::service::query_chapters_by_novel",
        depends=[
            "novels::service::non_contributor_cannot_query_restricted_novel",
            "novels::service::admin_can_query_restricted_novel",
            "novels::service::contributor_can_query_restricted_novel",
            "novels::service::guest_cannot_query_private_novel",
            "novels::service::admin_can_query_private_novel",
            "novels::service::contributor_can_query_viewer_restricted_novel",
            "novels::service::guest_cannot_query_viewer_restricted_novel",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestQueryChapterById:
    """Tests for query_chapter_by_id service function."""

    @pytest.mark.dependency(name="novels::service::non_contributor_cannot_query_restricted_chapter", scope="session")
    def test_non_contributor_cannot_query_restricted_chapter(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ):
        rt = p1_novels["rt"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, rt.novel_id, schemas.CreateChapter(chapter_num=0)
        )
        with pytest.raises(ChapterNotFoundException):
            query_chapter_by_id(test_db, p1_user_2, chapter.chapter_id)

    @pytest.mark.dependency(name="novels::service::guest_cannot_query_private_chapter", scope="session")
    def test_guest_cannot_query_private_chapter(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ):
        oe = p1_novels["oe"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(ChapterNotFoundException):
            query_chapter_by_id(test_db, None, chapter.chapter_id)

    @pytest.mark.dependency(name="novels::service::contributor_can_query_private_chapter", scope="session")
    def test_contributor_can_query_private_chapter(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ):
        oe = p1_novels["oe"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        query_chapter_by_id(test_db, p1_user_1, chapter.chapter_id)
        query_chapter_by_id(test_db, p1_user_2, chapter.chapter_id)

    @pytest.mark.dependency(name="novels::service::admin_can_query_private_chapter", scope="session")
    def test_admin_can_query_private_chapter(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_admin: User,
    ):
        oe = p1_novels["oe"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        query_chapter_by_id(test_db, p1_admin, chapter.chapter_id)

    @pytest.mark.dependency(name="novels::service::viewer_can_query_chapter", scope="session")
    def test_viewer_can_query_chapter(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ):
        ov = p1_novels["ov"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        query_chapter_by_id(test_db, p1_user_2, chapter.chapter_id)

    @pytest.mark.dependency(name="novels::service::guest_cannot_query_viewer_restricted_chapter", scope="session")
    def test_guest_cannot_query_viewer_restricted_chapter(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ):
        ov = p1_novels["ov"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(ChapterNotFoundException):
            query_chapter_by_id(test_db, None, chapter.chapter_id)

    @pytest.mark.dependency(
        name="gate::novels::service::query_chapter_by_id",
        depends=[
            "novels::service::non_contributor_cannot_query_restricted_chapter",
            "novels::service::guest_cannot_query_private_chapter",
            "novels::service::contributor_can_query_private_chapter",
            "novels::service::admin_can_query_private_chapter",
            "novels::service::viewer_can_query_chapter",
            "novels::service::guest_cannot_query_viewer_restricted_chapter",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestQueryChapterContentByMostRecent:
    """Tests for query_chapter_content_by_most_recent service function."""

    @pytest.mark.dependency(name="novels::service::non_contributor_cannot_query_restricted_content", scope="session")
    def test_non_contributor_cannot_query_restricted_content(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ):
        rt = p1_novels["rt"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, rt.novel_id, schemas.CreateChapter(chapter_num=0)
        )
        with pytest.raises(ChapterNotFoundException):
            query_chapter_content_by_most_recent(
                test_db, p1_user_2, chapter.chapter_id
            )

    @pytest.mark.dependency(name="novels::service::admin_can_query_restricted_content", scope="session")
    def test_admin_can_query_restricted_content(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_admin: User,
    ):
        rt = p1_novels["rt"]
        chapter, chapter_content = insert_chapter(
            test_db, p1_user_1, rt.novel_id, schemas.CreateChapter(chapter_num=0)
        )
        cc = query_chapter_content_by_most_recent(
            test_db, p1_admin, chapter.chapter_id
        )
        assert cc.chapter_content_id == chapter_content.chapter_content_id

    @pytest.mark.dependency(name="novels::service::contributor_can_query_restricted_content", scope="session")
    def test_contributor_can_query_restricted_content(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ):
        rt = p1_novels["rt"]
        chapter, chapter_content = insert_chapter(
            test_db, p1_user_1, rt.novel_id, schemas.CreateChapter(chapter_num=0)
        )
        cc = query_chapter_content_by_most_recent(
            test_db, p1_user_1, chapter.chapter_id
        )
        assert cc.chapter_content_id == chapter_content.chapter_content_id

    @pytest.mark.dependency(name="novels::service::guest_cannot_query_private_content", scope="session")
    def test_guest_cannot_query_private_content(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ):
        oe = p1_novels["oe"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(ChapterNotFoundException):
            query_chapter_content_by_most_recent(
                test_db, None, chapter.chapter_id
            )

    @pytest.mark.dependency(name="novels::service::contributor_can_query_private_content", scope="session")
    def test_contributor_can_query_private_content(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ):
        oe = p1_novels["oe"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        query_chapter_content_by_most_recent(
            test_db, p1_user_1, chapter.chapter_id
        )
        query_chapter_content_by_most_recent(
            test_db, p1_user_2, chapter.chapter_id
        )

    @pytest.mark.dependency(name="novels::service::admin_can_query_private_content", scope="session")
    def test_admin_can_query_private_content(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_admin: User,
    ):
        oe = p1_novels["oe"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        query_chapter_content_by_most_recent(
            test_db, p1_admin, chapter.chapter_id
        )

    @pytest.mark.dependency(name="novels::service::viewer_can_query_content", scope="session")
    def test_viewer_can_query_content(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
    ):
        ov = p1_novels["ov"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        query_chapter_content_by_most_recent(
            test_db, p1_user_2, chapter.chapter_id
        )

    @pytest.mark.dependency(name="novels::service::guest_cannot_query_viewer_restricted_content", scope="session")
    def test_guest_cannot_query_viewer_restricted_content(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
    ):
        ov = p1_novels["ov"]
        chapter, _ = insert_chapter(
            test_db, p1_user_1, ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(ChapterNotFoundException):
            query_chapter_content_by_most_recent(
                test_db, None, chapter.chapter_id
            )

    @pytest.mark.dependency(
        name="gate::novels::service::query_chapter_content_by_most_recent",
        depends=[
            "novels::service::non_contributor_cannot_query_restricted_content",
            "novels::service::admin_can_query_restricted_content",
            "novels::service::contributor_can_query_restricted_content",
            "novels::service::guest_cannot_query_private_content",
            "novels::service::contributor_can_query_private_content",
            "novels::service::admin_can_query_private_content",
            "novels::service::viewer_can_query_content",
            "novels::service::guest_cannot_query_viewer_restricted_content",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


class TestInsertChapterPermissions:
    """Tests for insert_chapter permission checks."""

    @pytest.mark.dependency(name="novels::service::viewer_cannot_insert_chapter", scope="session")
    def test_viewer_cannot_insert_chapter(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_2: User,
    ):
        ov = p1_novels["ov"]
        with pytest.raises(InsufficientPermissionsException):
            insert_chapter(
                test_db, p1_user_2, ov.novel_id, schemas.CreateChapter(chapter_num=2)
            )

    @pytest.mark.dependency(name="novels::service::admin_can_insert_chapter", scope="session")
    def test_admin_can_insert_chapter(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_admin: User,
    ):
        ov = p1_novels["ov"]
        chapter, content = insert_chapter(
            test_db, p1_admin, ov.novel_id, schemas.CreateChapter(chapter_num=2)
        )
        assert chapter.chapter_id is not None
        assert content.chapter_content_id is not None

    @pytest.mark.dependency(name="novels::service::chapter_content_count_after_inserts", scope="session")
    def test_chapter_content_count_after_inserts(
        self,
        test_db: Session,
        p1_novels: dict[str, Novel],
        p1_user_1: User,
        p1_user_2: User,
        p1_admin: User,
    ):
        """Verify total ChapterContent count after multiple inserts across novels."""
        rt = p1_novels["rt"]
        oe = p1_novels["oe"]
        ov = p1_novels["ov"]

        # 3 chapters on rt
        for i in range(3):
            insert_chapter(
                test_db, p1_user_1, rt.novel_id, schemas.CreateChapter(chapter_num=i)
            )
        # 2 chapters on oe (one per user)
        insert_chapter(
            test_db, p1_user_1, oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        insert_chapter(
            test_db, p1_user_2, oe.novel_id, schemas.CreateChapter(chapter_num=2)
        )
        # 2 chapters on ov (owner + admin)
        insert_chapter(
            test_db, p1_user_1, ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        insert_chapter(
            test_db, p1_admin, ov.novel_id, schemas.CreateChapter(chapter_num=2)
        )

        assert len(test_db.execute(select(ChapterContent)).scalars().all()) == 7

    @pytest.mark.dependency(
        name="gate::novels::service::insert_chapter_permissions",
        depends=[
            "novels::service::viewer_cannot_insert_chapter",
            "novels::service::admin_can_insert_chapter",
            "novels::service::chapter_content_count_after_inserts",
        ],
        scope="session",
    )
    def test_class_gate(self):
        pass


@pytest.mark.order("last")
@pytest.mark.dependency(
    name="gate::novels::service",
    depends=[
        "gate::novels::service::query_novels_by_title",
        "gate::novels::service::query_novel_by_id",
        "gate::novels::service::query_chapters_by_novel",
        "gate::novels::service::query_chapter_by_id",
        "gate::novels::service::query_chapter_content_by_most_recent",
        "gate::novels::service::insert_chapter_permissions",
    ],
    scope="session",
)
def test_gate():
    """All novels service tests must pass before downstream layers run."""
    pass
