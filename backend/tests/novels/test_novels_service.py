"""
Service-level permission and contract tests for novels and chapters.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import InsufficientPermissionsException
from src.novels import schemas
from src.novels.constants import NovelType, Visibility
from src.novels.exceptions import (
    ChapterNotFoundException,
    NovelNotFoundException,
)
from src.novels.service import (
    insert_chapter,
    query_chapter_by_id,
    query_chapter_content_by_most_recent,
    query_chapters_by_novel,
    query_novel_by_id,
    query_novels_by_title,
)
from test_support.test_data.scenarios import DatabaseScenario


async def test_query_novels_by_title(async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario) -> None:
    s = novel_access_scenario
    for actor in (None, s.users["owner"], s.users["other"], s.users["admin"]):
        results = await query_novels_by_title(async_test_db, actor, "")
        assert {n.novel_title for n in results} == {"pt", "ps"}

    filtered = await query_novels_by_title(async_test_db, None, "t")
    assert [n.novel_title for n in filtered] == ["pt"]


async def test_query_novel_by_id(async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario) -> None:
    s = novel_access_scenario

    us = await query_novel_by_id(async_test_db, None, s.novels["us"].novel_id)
    assert (us.novel_title, us.novel_visibility, us.novel_type) == ("us", Visibility.UNLISTED, NovelType.ORIGINAL)

    rt = await query_novel_by_id(async_test_db, s.users["owner"], s.novels["rt"].novel_id)
    assert (rt.novel_title, rt.novel_visibility) == ("rt", Visibility.RESTRICTED)

    prt = await query_novel_by_id(async_test_db, s.users["admin"], s.novels["prt"].novel_id)
    assert (prt.novel_title, prt.novel_visibility) == ("prt", Visibility.PRIVATE)

    oe_editor = await query_novel_by_id(async_test_db, s.users["other"], s.novels["oe"].novel_id)
    assert oe_editor.novel_title == "oe"

    for actor, novel_key in ((None, "rt"), (None, "prt"), (s.users["other"], "prt")):
        with pytest.raises(NovelNotFoundException):
            await query_novel_by_id(async_test_db, actor, s.novels[novel_key].novel_id)


async def test_query_chapters_by_novel(async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario) -> None:
    s = novel_access_scenario
    rt, ov = s.novels["rt"], s.novels["ov"]
    for i in range(3):
        await insert_chapter(async_test_db, s.users["owner"], rt.novel_id, schemas.CreateChapter(chapter_num=i))
    await insert_chapter(async_test_db, s.users["owner"], ov.novel_id, schemas.CreateChapter(chapter_num=1))

    assert len(await query_chapters_by_novel(async_test_db, s.users["owner"], rt.novel_id, start=None, end=None)) == 3
    assert len(await query_chapters_by_novel(async_test_db, s.users["admin"], rt.novel_id, start=None, end=None)) == 3
    assert len(await query_chapters_by_novel(async_test_db, s.users["other"], ov.novel_id, start=None, end=None)) == 1

    for actor, novel_id in ((s.users["other"], rt.novel_id), (None, ov.novel_id)):
        with pytest.raises(NovelNotFoundException):
            await query_chapters_by_novel(async_test_db, actor, novel_id, start=None, end=None)


async def test_query_chapter_by_id(async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario) -> None:
    s = novel_access_scenario
    rt_ch, _ = await insert_chapter(
        async_test_db, s.users["owner"], s.novels["rt"].novel_id, schemas.CreateChapter(chapter_num=0)
    )
    ov_ch, _ = await insert_chapter(
        async_test_db, s.users["owner"], s.novels["ov"].novel_id, schemas.CreateChapter(chapter_num=1)
    )

    assert (await query_chapter_by_id(async_test_db, s.users["owner"], rt_ch.chapter_id)).chapter_id == rt_ch.chapter_id
    assert (await query_chapter_by_id(async_test_db, s.users["admin"], rt_ch.chapter_id)).chapter_id == rt_ch.chapter_id
    assert (await query_chapter_by_id(async_test_db, s.users["other"], ov_ch.chapter_id)).chapter_id == ov_ch.chapter_id

    for actor, chapter_id in ((s.users["other"], rt_ch.chapter_id), (None, ov_ch.chapter_id)):
        with pytest.raises(ChapterNotFoundException):
            await query_chapter_by_id(async_test_db, actor, chapter_id)


async def test_query_chapter_content_by_most_recent(
    async_test_db: AsyncSession, novel_permission_scenario: DatabaseScenario
) -> None:
    s = novel_permission_scenario
    public_ch = s.chapters["public"]
    private_ch = s.chapters["private"]

    # Public chapter has v1 and v2; must return the latest version.
    latest = await query_chapter_content_by_most_recent(async_test_db, None, public_ch.chapter_id)
    assert latest.chapter_content_id == s.contents["public_v2"].chapter_content_id

    owner_private = await query_chapter_content_by_most_recent(async_test_db, s.users["owner"], private_ch.chapter_id)
    assert owner_private.chapter_content_id == s.contents["private_v1"].chapter_content_id
    admin_private = await query_chapter_content_by_most_recent(async_test_db, s.users["admin"], private_ch.chapter_id)
    assert admin_private.chapter_content_id == s.contents["private_v1"].chapter_content_id

    for actor in (None, s.users["other"]):
        with pytest.raises(ChapterNotFoundException):
            await query_chapter_content_by_most_recent(async_test_db, actor, private_ch.chapter_id)


async def test_insert_chapter_permissions(
    async_test_db: AsyncSession, novel_access_scenario: DatabaseScenario
) -> None:
    s = novel_access_scenario
    ov = s.novels["ov"]

    with pytest.raises(InsufficientPermissionsException):
        await insert_chapter(async_test_db, s.users["other"], ov.novel_id, schemas.CreateChapter(chapter_num=2))

    chapter, content = await insert_chapter(
        async_test_db, s.users["admin"], ov.novel_id, schemas.CreateChapter(chapter_num=2)
    )
    assert chapter.chapter_id is not None
    assert content.chapter_content_id is not None
