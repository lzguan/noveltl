"""
Todo: Clean this file up later
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


def test_novels_query_permissions(
    test_db: Session,
    p1_novels: dict[str, Novel],
    p1_user_1: User,  # tyrone
    p1_user_2: User,  # speed
    p1_admin: User,
):
    public_novels_u_none = query_novels_by_title(test_db, None, "")
    assert len(public_novels_u_none) == 2
    novel_titles = [novel.novel_title for novel in public_novels_u_none]
    assert "pt" in novel_titles
    assert "ps" in novel_titles

    public_novels_u_1 = query_novels_by_title(test_db, p1_user_1, "")
    assert len(public_novels_u_1) == 2
    novel_titles = [novel.novel_title for novel in public_novels_u_1]
    assert "pt" in novel_titles
    assert "ps" in novel_titles

    public_novels_u_2 = query_novels_by_title(test_db, p1_user_2, "")
    assert len(public_novels_u_2) == 2
    novel_titles = [novel.novel_title for novel in public_novels_u_2]
    assert "pt" in novel_titles
    assert "ps" in novel_titles

    public_novels_u_admin = query_novels_by_title(test_db, p1_admin, "")
    assert len(public_novels_u_admin) == 2
    novel_titles = [novel.novel_title for novel in public_novels_u_admin]
    assert "pt" in novel_titles
    assert "ps" in novel_titles

    public_novels_u_none_search_t = query_novels_by_title(test_db, None, "t")
    assert len(public_novels_u_none_search_t) == 1
    assert public_novels_u_none_search_t[0].novel_title == "pt"

    us = query_novel_by_id(test_db, p1_user_2, p1_novels["us"].novel_id)
    assert us.novel_title == "us"
    assert us.novel_visibility == Visibility.UNLISTED
    assert us.novel_type == NovelType.ORIGINAL

    query_novel_by_id(test_db, None, p1_novels["us"].novel_id)
    query_novel_by_id(test_db, p1_user_1, p1_novels["us"].novel_id)
    with pytest.raises(NovelNotFoundException):
        query_novel_by_id(test_db, None, p1_novels["rt"].novel_id)

    rt = query_novel_by_id(test_db, p1_user_1, p1_novels["rt"].novel_id)
    assert rt.novel_title == "rt"
    assert rt.novel_visibility == Visibility.RESTRICTED
    assert rt.novel_type == NovelType.ORIGINAL

    with pytest.raises(NovelNotFoundException):
        query_novel_by_id(test_db, None, p1_novels["prt"].novel_id)

    prt = query_novel_by_id(test_db, p1_admin, p1_novels["prt"].novel_id)
    assert prt.novel_title == "prt"
    assert prt.novel_visibility == Visibility.PRIVATE
    assert prt.novel_type == NovelType.ORIGINAL

    oe = query_novel_by_id(test_db, p1_user_1, p1_novels["oe"].novel_id)
    assert oe.novel_title == "oe"
    assert oe.novel_visibility == Visibility.PRIVATE

    assert (
        oe.novel_title
        == query_novel_by_id(test_db, p1_user_2, p1_novels["oe"].novel_id).novel_title
    )
    with pytest.raises(NovelNotFoundException):
        query_novel_by_id(test_db, None, p1_novels["oe"].novel_id)


def test_chapters_query_permissions(
    test_db: Session,
    p1_novels: dict[str, Novel],
    p1_user_1: User,  # tyrone
    p1_user_2: User,  # speed
    p1_admin: User,
):
    rt = query_novel_by_id(test_db, p1_user_1, p1_novels["rt"].novel_id)
    rt_chapters_and_contents = [
        insert_chapter(
            test_db, p1_user_1, rt.novel_id, schemas.CreateChapter(chapter_num=i)
        )
        for i in range(3)
    ]

    with pytest.raises(NovelNotFoundException):
        query_chapters_by_novel(
            test_db, p1_user_2, rt.novel_id, start=None, end=None
        )
    rt_chapters_u_admin = query_chapters_by_novel(
        test_db, p1_admin, rt.novel_id, start=None, end=None
    )
    assert len(rt_chapters_u_admin) == 3
    rt_chapters_u_1 = query_chapters_by_novel(
        test_db, p1_user_1, rt.novel_id, start=None, end=None
    )
    assert len(rt_chapters_u_1) == 3

    with pytest.raises(ChapterNotFoundException):
        query_chapter_by_id(test_db, p1_user_2, rt_chapters_and_contents[0][0].chapter_id)

    for chapter, chapter_content in rt_chapters_and_contents:
        with pytest.raises(ChapterNotFoundException):
            query_chapter_content_by_most_recent(
                test_db, p1_user_2, chapter.chapter_id
            )
        cc_u_admin = query_chapter_content_by_most_recent(
            test_db, p1_admin, chapter.chapter_id
        )
        assert cc_u_admin.chapter_content_id == chapter_content.chapter_content_id
        cc_u_1 = query_chapter_content_by_most_recent(
            test_db, p1_user_1, chapter.chapter_id
        )
        assert cc_u_1.chapter_content_id == chapter_content.chapter_content_id

    oe = p1_novels["oe"]
    oe_chapter_1, _ = insert_chapter(
        test_db, p1_user_1, oe.novel_id, schemas.CreateChapter(chapter_num=1)
    )

    assert len(test_db.execute(select(ChapterContent)).scalars().all()) == 4

    query_chapter_by_id(test_db, p1_user_1, oe_chapter_1.chapter_id)
    query_chapter_content_by_most_recent(
        test_db, p1_user_1, oe_chapter_1.chapter_id
    )

    query_chapter_by_id(test_db, p1_user_2, oe_chapter_1.chapter_id)
    query_chapter_content_by_most_recent(
        test_db, p1_user_2, oe_chapter_1.chapter_id
    )

    oe_chapter_2, _ = insert_chapter(
        test_db, p1_user_2, oe.novel_id, schemas.CreateChapter(chapter_num=2)
    )

    assert len(test_db.execute(select(ChapterContent)).scalars().all()) == 5
    query_chapter_by_id(test_db, p1_user_1, oe_chapter_2.chapter_id)
    query_chapter_content_by_most_recent(
        test_db, p1_user_1, oe_chapter_2.chapter_id
    )

    query_chapter_by_id(test_db, p1_user_2, oe_chapter_2.chapter_id)
    query_chapter_content_by_most_recent(
        test_db, p1_user_2, oe_chapter_2.chapter_id
    )

    with pytest.raises(NovelNotFoundException):
        query_chapters_by_novel(test_db, None, oe.novel_id, start=None, end=None)
    with pytest.raises(ChapterNotFoundException):
        query_chapter_by_id(test_db, None, oe_chapter_1.chapter_id)
    with pytest.raises(ChapterNotFoundException):
        query_chapter_content_by_most_recent(
            test_db, None, oe_chapter_1.chapter_id
        )

    # assert admin can access
    query_chapters_by_novel(test_db, p1_admin, oe.novel_id, start=None, end=None)
    query_chapter_by_id(test_db, p1_admin, oe_chapter_1.chapter_id)
    query_chapter_content_by_most_recent(
        test_db, p1_admin, oe_chapter_1.chapter_id
    )

    ov = p1_novels["ov"]
    ov_chapter_1, _ = insert_chapter(
        test_db, p1_user_1, ov.novel_id, schemas.CreateChapter(chapter_num=1)
    )
    query_chapters_by_novel(test_db, p1_user_2, ov.novel_id, start=None, end=None)
    query_chapter_by_id(test_db, p1_user_2, ov_chapter_1.chapter_id)
    query_chapter_content_by_most_recent(
        test_db, p1_user_2, ov_chapter_1.chapter_id
    )
    with pytest.raises(NovelNotFoundException):
        query_chapters_by_novel(test_db, None, ov.novel_id, start=None, end=None)
    with pytest.raises(ChapterNotFoundException):
        query_chapter_by_id(test_db, None, ov_chapter_1.chapter_id)
    with pytest.raises(ChapterNotFoundException):
        query_chapter_content_by_most_recent(
            test_db, None, ov_chapter_1.chapter_id
        )

    # assert p1_user_2 cannot create chapters (viewer role)
    with pytest.raises(InsufficientPermissionsException):
        insert_chapter(
            test_db, p1_user_2, ov.novel_id, schemas.CreateChapter(chapter_num=2)
        )

    # assert admin can create chapters
    ov_chapter_2, ov_content_2 = insert_chapter(
        test_db, p1_admin, ov.novel_id, schemas.CreateChapter(chapter_num=2)
    )
    assert ov_chapter_2.chapter_id is not None
    assert ov_content_2.chapter_content_id is not None

    # check overall number of chapter contents
    assert len(test_db.execute(select(ChapterContent)).scalars().all()) == 7
