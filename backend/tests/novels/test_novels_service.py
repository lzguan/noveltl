"""
Service-level permission tests for novels and chapters.

Tests query_novels_by_title, query_novel_by_id, query_chapters_by_novel,
query_chapter_by_id, query_chapter_content_by_most_recent, and
insert_chapter permission behavior.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.exceptions import InsufficientPermissionsException
from src.novels import schemas
from src.novels.constants import NovelType, Visibility
from src.novels.exceptions import (
    ChapterNotFoundException,
    NovelNotFoundException,
)
from src.novels.models import ChapterContent
from src.novels.service import (
    insert_chapter,
    query_chapter_by_id,
    query_chapter_content_by_most_recent,
    query_chapters_by_novel,
    query_novel_by_id,
    query_novels_by_title,
)
from test_support.test_data.scenarios import DatabaseScenario


class TestQueryNovelsByTitle:
    """Tests for query_novels_by_title service function."""

    async def test_guest_sees_public_novels(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        results = await query_novels_by_title(async_test_db, None, "")
        assert len(results) == 2
        titles = [n.novel_title for n in results]
        assert "pt" in titles
        assert "ps" in titles

    async def test_regular_user_sees_public_novels(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        results = await query_novels_by_title(async_test_db, novel_access_scenario.users["owner"], "")
        assert len(results) == 2
        titles = [n.novel_title for n in results]
        assert "pt" in titles
        assert "ps" in titles

    async def test_other_user_sees_public_novels(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        results = await query_novels_by_title(async_test_db, novel_access_scenario.users["other"], "")
        assert len(results) == 2
        titles = [n.novel_title for n in results]
        assert "pt" in titles
        assert "ps" in titles

    async def test_admin_sees_public_novels(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        results = await query_novels_by_title(async_test_db, novel_access_scenario.users["admin"], "")
        assert len(results) == 2
        titles = [n.novel_title for n in results]
        assert "pt" in titles
        assert "ps" in titles

    async def test_search_filters_by_title(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        results = await query_novels_by_title(async_test_db, None, "t")
        assert len(results) == 1
        assert results[0].novel_title == "pt"


class TestQueryNovelById:
    """Tests for query_novel_by_id service function."""

    async def test_unlisted_novel_visible_to_contributor(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        us = await query_novel_by_id(
            async_test_db, novel_access_scenario.users["other"], novel_access_scenario.novels["us"].novel_id
        )
        assert us.novel_title == "us"
        assert us.novel_visibility == Visibility.UNLISTED
        assert us.novel_type == NovelType.ORIGINAL

    async def test_unlisted_novel_visible_to_guest(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        await query_novel_by_id(async_test_db, None, novel_access_scenario.novels["us"].novel_id)

    async def test_unlisted_novel_visible_to_other_user(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        await query_novel_by_id(
            async_test_db, novel_access_scenario.users["owner"], novel_access_scenario.novels["us"].novel_id
        )

    async def test_restricted_novel_not_visible_to_guest(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        with pytest.raises(NovelNotFoundException):
            await query_novel_by_id(async_test_db, None, novel_access_scenario.novels["rt"].novel_id)

    async def test_restricted_novel_visible_to_contributor(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        rt = await query_novel_by_id(
            async_test_db, novel_access_scenario.users["owner"], novel_access_scenario.novels["rt"].novel_id
        )
        assert rt.novel_title == "rt"
        assert rt.novel_visibility == Visibility.RESTRICTED
        assert rt.novel_type == NovelType.ORIGINAL

    async def test_private_novel_not_visible_to_guest(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        with pytest.raises(NovelNotFoundException):
            await query_novel_by_id(async_test_db, None, novel_access_scenario.novels["prt"].novel_id)

    async def test_private_novel_visible_to_admin(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        prt = await query_novel_by_id(
            async_test_db, novel_access_scenario.users["admin"], novel_access_scenario.novels["prt"].novel_id
        )
        assert prt.novel_title == "prt"
        assert prt.novel_visibility == Visibility.PRIVATE
        assert prt.novel_type == NovelType.ORIGINAL

    async def test_private_novel_visible_to_owner(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe = await query_novel_by_id(
            async_test_db, novel_access_scenario.users["owner"], novel_access_scenario.novels["oe"].novel_id
        )
        assert oe.novel_title == "oe"
        assert oe.novel_visibility == Visibility.PRIVATE

    async def test_private_novel_visible_to_both_contributors(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe_u1 = await query_novel_by_id(
            async_test_db, novel_access_scenario.users["owner"], novel_access_scenario.novels["oe"].novel_id
        )
        oe_u2 = await query_novel_by_id(
            async_test_db, novel_access_scenario.users["other"], novel_access_scenario.novels["oe"].novel_id
        )
        assert oe_u1.novel_title == oe_u2.novel_title

    async def test_private_novel_not_visible_to_non_contributor(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        with pytest.raises(NovelNotFoundException):
            await query_novel_by_id(async_test_db, None, novel_access_scenario.novels["oe"].novel_id)


class TestQueryChaptersByNovel:
    """Tests for query_chapters_by_novel service function."""

    async def test_non_contributor_cannot_query_restricted_novel(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        rt = novel_access_scenario.novels["rt"]
        for i in range(3):
            await insert_chapter(
                async_test_db, novel_access_scenario.users["owner"], rt.novel_id, schemas.CreateChapter(chapter_num=i)
            )
        with pytest.raises(NovelNotFoundException):
            await query_chapters_by_novel(
                async_test_db, novel_access_scenario.users["other"], rt.novel_id, start=None, end=None
            )

    async def test_admin_can_query_restricted_novel(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        rt = novel_access_scenario.novels["rt"]
        for i in range(3):
            await insert_chapter(
                async_test_db, novel_access_scenario.users["owner"], rt.novel_id, schemas.CreateChapter(chapter_num=i)
            )
        chapters = await query_chapters_by_novel(
            async_test_db, novel_access_scenario.users["admin"], rt.novel_id, start=None, end=None
        )
        assert len(chapters) == 3

    async def test_contributor_can_query_restricted_novel(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        rt = novel_access_scenario.novels["rt"]
        for i in range(3):
            await insert_chapter(
                async_test_db, novel_access_scenario.users["owner"], rt.novel_id, schemas.CreateChapter(chapter_num=i)
            )
        chapters = await query_chapters_by_novel(
            async_test_db, novel_access_scenario.users["owner"], rt.novel_id, start=None, end=None
        )
        assert len(chapters) == 3

    async def test_guest_cannot_query_private_novel(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe = novel_access_scenario.novels["oe"]
        with pytest.raises(NovelNotFoundException):
            await query_chapters_by_novel(async_test_db, None, oe.novel_id, start=None, end=None)

    async def test_admin_can_query_private_novel(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe = novel_access_scenario.novels["oe"]
        await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        chapters = await query_chapters_by_novel(
            async_test_db, novel_access_scenario.users["admin"], oe.novel_id, start=None, end=None
        )
        assert len(chapters) == 1

    async def test_contributor_can_query_viewer_restricted_novel(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        ov = novel_access_scenario.novels["ov"]
        await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        chapters = await query_chapters_by_novel(
            async_test_db, novel_access_scenario.users["other"], ov.novel_id, start=None, end=None
        )
        assert len(chapters) == 1

    async def test_guest_cannot_query_viewer_restricted_novel(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        ov = novel_access_scenario.novels["ov"]
        await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(NovelNotFoundException):
            await query_chapters_by_novel(async_test_db, None, ov.novel_id, start=None, end=None)


class TestQueryChapterById:
    """Tests for query_chapter_by_id service function."""

    async def test_non_contributor_cannot_query_restricted_chapter(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        rt = novel_access_scenario.novels["rt"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], rt.novel_id, schemas.CreateChapter(chapter_num=0)
        )
        with pytest.raises(ChapterNotFoundException):
            await query_chapter_by_id(async_test_db, novel_access_scenario.users["other"], chapter.chapter_id)

    async def test_guest_cannot_query_private_chapter(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe = novel_access_scenario.novels["oe"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(ChapterNotFoundException):
            await query_chapter_by_id(async_test_db, None, chapter.chapter_id)

    async def test_contributor_can_query_private_chapter(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe = novel_access_scenario.novels["oe"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        await query_chapter_by_id(async_test_db, novel_access_scenario.users["owner"], chapter.chapter_id)
        await query_chapter_by_id(async_test_db, novel_access_scenario.users["other"], chapter.chapter_id)

    async def test_admin_can_query_private_chapter(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe = novel_access_scenario.novels["oe"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        await query_chapter_by_id(async_test_db, novel_access_scenario.users["admin"], chapter.chapter_id)

    async def test_viewer_can_query_chapter(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        ov = novel_access_scenario.novels["ov"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        await query_chapter_by_id(async_test_db, novel_access_scenario.users["other"], chapter.chapter_id)

    async def test_guest_cannot_query_viewer_restricted_chapter(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        ov = novel_access_scenario.novels["ov"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(ChapterNotFoundException):
            await query_chapter_by_id(async_test_db, None, chapter.chapter_id)


class TestQueryChapterContentByMostRecent:
    """Tests for query_chapter_content_by_most_recent service function."""

    async def test_non_contributor_cannot_query_restricted_content(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        rt = novel_access_scenario.novels["rt"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], rt.novel_id, schemas.CreateChapter(chapter_num=0)
        )
        with pytest.raises(ChapterNotFoundException):
            await query_chapter_content_by_most_recent(
                async_test_db, novel_access_scenario.users["other"], chapter.chapter_id
            )

    async def test_admin_can_query_restricted_content(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        rt = novel_access_scenario.novels["rt"]
        chapter, chapter_content = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], rt.novel_id, schemas.CreateChapter(chapter_num=0)
        )
        cc = await query_chapter_content_by_most_recent(
            async_test_db, novel_access_scenario.users["admin"], chapter.chapter_id
        )
        assert cc.chapter_content_id == chapter_content.chapter_content_id

    async def test_contributor_can_query_restricted_content(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        rt = novel_access_scenario.novels["rt"]
        chapter, chapter_content = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], rt.novel_id, schemas.CreateChapter(chapter_num=0)
        )
        cc = await query_chapter_content_by_most_recent(
            async_test_db, novel_access_scenario.users["owner"], chapter.chapter_id
        )
        assert cc.chapter_content_id == chapter_content.chapter_content_id

    async def test_guest_cannot_query_private_content(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe = novel_access_scenario.novels["oe"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(ChapterNotFoundException):
            await query_chapter_content_by_most_recent(async_test_db, None, chapter.chapter_id)

    async def test_contributor_can_query_private_content(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe = novel_access_scenario.novels["oe"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        await query_chapter_content_by_most_recent(
            async_test_db, novel_access_scenario.users["owner"], chapter.chapter_id
        )
        await query_chapter_content_by_most_recent(
            async_test_db, novel_access_scenario.users["other"], chapter.chapter_id
        )

    async def test_admin_can_query_private_content(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        oe = novel_access_scenario.novels["oe"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        await query_chapter_content_by_most_recent(
            async_test_db, novel_access_scenario.users["admin"], chapter.chapter_id
        )

    async def test_viewer_can_query_content(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        ov = novel_access_scenario.novels["ov"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        await query_chapter_content_by_most_recent(
            async_test_db, novel_access_scenario.users["other"], chapter.chapter_id
        )

    async def test_guest_cannot_query_viewer_restricted_content(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        ov = novel_access_scenario.novels["ov"]
        chapter, _ = await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        with pytest.raises(ChapterNotFoundException):
            await query_chapter_content_by_most_recent(async_test_db, None, chapter.chapter_id)


class TestInsertChapterPermissions:
    """Tests for insert_chapter permission checks."""

    async def test_viewer_cannot_insert_chapter(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        ov = novel_access_scenario.novels["ov"]
        with pytest.raises(InsufficientPermissionsException):
            await insert_chapter(
                async_test_db, novel_access_scenario.users["other"], ov.novel_id, schemas.CreateChapter(chapter_num=2)
            )

    async def test_admin_can_insert_chapter(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        ov = novel_access_scenario.novels["ov"]
        chapter, content = await insert_chapter(
            async_test_db, novel_access_scenario.users["admin"], ov.novel_id, schemas.CreateChapter(chapter_num=2)
        )
        assert chapter.chapter_id is not None
        assert content.chapter_content_id is not None

    async def test_chapter_content_count_after_inserts(
        self, test_db: Session, async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
    ):
        """Verify total ChapterContent count after multiple inserts across novels."""
        rt = novel_access_scenario.novels["rt"]
        oe = novel_access_scenario.novels["oe"]
        ov = novel_access_scenario.novels["ov"]

        # 3 chapters on rt
        for i in range(3):
            await insert_chapter(
                async_test_db, novel_access_scenario.users["owner"], rt.novel_id, schemas.CreateChapter(chapter_num=i)
            )
        # 2 chapters on oe (one per user)
        await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], oe.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        await insert_chapter(
            async_test_db, novel_access_scenario.users["other"], oe.novel_id, schemas.CreateChapter(chapter_num=2)
        )
        # 2 chapters on ov (owner + admin)
        await insert_chapter(
            async_test_db, novel_access_scenario.users["owner"], ov.novel_id, schemas.CreateChapter(chapter_num=1)
        )
        await insert_chapter(
            async_test_db, novel_access_scenario.users["admin"], ov.novel_id, schemas.CreateChapter(chapter_num=2)
        )

        assert len(test_db.execute(select(ChapterContent)).scalars().all()) == 7
