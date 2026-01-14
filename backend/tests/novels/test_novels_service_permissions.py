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
    NovelNotFoundException,
    RawChapterNotFoundException,
    RawChapterRevisionNotFoundException,
)
from src.novels.models import Novel, RawChapterRevision
from src.novels.service import (
    insert_raw_chapter,
    insert_raw_chapter_revision,
    query_novel_by_id,
    query_novels_by_title,
    query_raw_chapter_by_id,
    query_raw_chapter_revision_by_id,
    query_raw_chapter_revisions_by_novel,
    query_raw_chapters_by_novel,
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
    rt_chapters = [
        insert_raw_chapter(
            test_db, p1_user_1, rt.novel_id, schemas.CreateRawChapter(raw_chapter_num=i)
        )
        for i in range(3)
    ]
    rt_revisions = [
        insert_raw_chapter_revision(
            test_db,
            p1_user_1,
            chapter.raw_chapter_id,
            schemas.CreateRawChapterRevision(
                raw_chapter_revision_text=f"Text {chapter.raw_chapter_num}",
                raw_chapter_revision_title=f"Title {chapter.raw_chapter_num}",
            ),
        )
        for chapter in rt_chapters
    ]

    with pytest.raises(NovelNotFoundException):
        query_raw_chapters_by_novel(
            test_db, p1_user_2, rt.novel_id, start=None, end=None
        )
    rt_chapters_u_admin = query_raw_chapters_by_novel(
        test_db, p1_admin, rt.novel_id, start=None, end=None
    )
    assert len(rt_chapters_u_admin) == 3
    rt_chapters_u_1 = query_raw_chapters_by_novel(
        test_db, p1_user_1, rt.novel_id, start=None, end=None
    )
    assert len(rt_chapters_u_1) == 3

    with pytest.raises(RawChapterNotFoundException):
        query_raw_chapter_by_id(test_db, p1_user_2, rt_chapters[0].raw_chapter_id)
    rt_revisions_u_admin = query_raw_chapter_revisions_by_novel(
        test_db,
        p1_admin,
        rt.novel_id,
        is_public=None,
        is_primary=None,
        is_final=None,
        start=None,
        end=None,
    )
    assert len(rt_revisions_u_admin) == 3
    rt_revisions_u_1 = query_raw_chapter_revisions_by_novel(
        test_db,
        p1_user_1,
        rt.novel_id,
        is_public=None,
        is_primary=None,
        is_final=None,
        start=None,
        end=None,
    )
    assert len(rt_revisions_u_1) == 3

    for revision in rt_revisions:
        with pytest.raises(RawChapterRevisionNotFoundException):
            query_raw_chapter_revision_by_id(
                test_db, p1_user_2, revision.raw_chapter_revision_id
            )
        rev_u_admin = query_raw_chapter_revision_by_id(
            test_db, p1_admin, revision.raw_chapter_revision_id
        )
        assert rev_u_admin.raw_chapter_revision_id == revision.raw_chapter_revision_id
        rev_u_1 = query_raw_chapter_revision_by_id(
            test_db, p1_user_1, revision.raw_chapter_revision_id
        )
        assert rev_u_1.raw_chapter_revision_id == revision.raw_chapter_revision_id

    oe = p1_novels["oe"]
    oe_chapter_1 = insert_raw_chapter(
        test_db, p1_user_1, oe.novel_id, schemas.CreateRawChapter(raw_chapter_num=1)
    )
    oe_revision_1 = insert_raw_chapter_revision(
        test_db,
        p1_user_1,
        oe_chapter_1.raw_chapter_id,
        schemas.CreateRawChapterRevision(
            raw_chapter_revision_text="Owner Editor Text",
            raw_chapter_revision_title="Owner Editor Title",
        ),
    )

    assert len(test_db.execute(select(RawChapterRevision)).scalars().all()) == 4

    query_raw_chapter_by_id(test_db, p1_user_1, oe_chapter_1.raw_chapter_id)
    query_raw_chapter_revision_by_id(
        test_db, p1_user_1, oe_revision_1.raw_chapter_revision_id
    )
    assert (
        len(
            query_raw_chapter_revisions_by_novel(
                test_db,
                p1_user_1,
                oe.novel_id,
                is_public=None,
                is_primary=None,
                is_final=None,
                start=None,
                end=None,
            )
        )
        == 1
    )

    query_raw_chapter_by_id(test_db, p1_user_2, oe_chapter_1.raw_chapter_id)
    query_raw_chapter_revision_by_id(
        test_db, p1_user_2, oe_revision_1.raw_chapter_revision_id
    )
    assert (
        len(
            query_raw_chapter_revisions_by_novel(
                test_db,
                p1_user_2,
                oe.novel_id,
                is_public=None,
                is_primary=None,
                is_final=None,
                start=None,
                end=None,
            )
        )
        == 1
    )

    oe_chapter_2 = insert_raw_chapter(
        test_db, p1_user_2, oe.novel_id, schemas.CreateRawChapter(raw_chapter_num=2)
    )
    oe_revision_2 = insert_raw_chapter_revision(
        test_db,
        p1_user_2,
        oe_chapter_2.raw_chapter_id,
        schemas.CreateRawChapterRevision(
            raw_chapter_revision_text="Shared Editor Text",
            raw_chapter_revision_title="Shared Editor Title",
        ),
    )

    assert len(test_db.execute(select(RawChapterRevision)).scalars().all()) == 5
    query_raw_chapter_by_id(test_db, p1_user_1, oe_chapter_2.raw_chapter_id)
    query_raw_chapter_revision_by_id(
        test_db, p1_user_1, oe_revision_2.raw_chapter_revision_id
    )
    assert (
        len(
            query_raw_chapter_revisions_by_novel(
                test_db,
                p1_user_1,
                oe.novel_id,
                is_public=None,
                is_primary=None,
                is_final=None,
                start=None,
                end=None,
            )
        )
        == 2
    )

    query_raw_chapter_by_id(test_db, p1_user_2, oe_chapter_2.raw_chapter_id)
    query_raw_chapter_revision_by_id(
        test_db, p1_user_2, oe_revision_2.raw_chapter_revision_id
    )
    assert (
        len(
            query_raw_chapter_revisions_by_novel(
                test_db,
                p1_user_2,
                oe.novel_id,
                is_public=None,
                is_primary=None,
                is_final=None,
                start=None,
                end=None,
            )
        )
        == 2
    )

    with pytest.raises(NovelNotFoundException):
        query_raw_chapters_by_novel(test_db, None, oe.novel_id, start=None, end=None)
    with pytest.raises(RawChapterNotFoundException):
        query_raw_chapter_by_id(test_db, None, oe_chapter_1.raw_chapter_id)
    with pytest.raises(RawChapterRevisionNotFoundException):
        query_raw_chapter_revision_by_id(
            test_db, None, oe_revision_1.raw_chapter_revision_id
        )

    # assert admin can access
    query_raw_chapters_by_novel(test_db, p1_admin, oe.novel_id, start=None, end=None)
    query_raw_chapter_by_id(test_db, p1_admin, oe_chapter_1.raw_chapter_id)
    query_raw_chapter_revision_by_id(
        test_db, p1_admin, oe_revision_1.raw_chapter_revision_id
    )

    ov = p1_novels["ov"]
    ov_chapter_1 = insert_raw_chapter(
        test_db, p1_user_1, ov.novel_id, schemas.CreateRawChapter(raw_chapter_num=1)
    )
    ov_revision_1 = insert_raw_chapter_revision(
        test_db,
        p1_user_1,
        ov_chapter_1.raw_chapter_id,
        schemas.CreateRawChapterRevision(
            raw_chapter_revision_text="Owner Viewer Text",
            raw_chapter_revision_title="Owner Viewer Title",
        ),
    )
    query_raw_chapters_by_novel(test_db, p1_user_2, ov.novel_id, start=None, end=None)
    query_raw_chapter_by_id(test_db, p1_user_2, ov_chapter_1.raw_chapter_id)
    query_raw_chapter_revision_by_id(
        test_db, p1_user_2, ov_revision_1.raw_chapter_revision_id
    )
    with pytest.raises(NovelNotFoundException):
        query_raw_chapters_by_novel(test_db, None, ov.novel_id, start=None, end=None)
    with pytest.raises(RawChapterNotFoundException):
        query_raw_chapter_by_id(test_db, None, ov_chapter_1.raw_chapter_id)
    with pytest.raises(RawChapterRevisionNotFoundException):
        query_raw_chapter_revision_by_id(
            test_db, None, ov_revision_1.raw_chapter_revision_id
        )

    # assert p1_user_2 cannot create chapters or revisions
    with pytest.raises(InsufficientPermissionsException):
        insert_raw_chapter(
            test_db, p1_user_2, ov.novel_id, schemas.CreateRawChapter(raw_chapter_num=2)
        )
    with pytest.raises(InsufficientPermissionsException):
        insert_raw_chapter_revision(
            test_db,
            p1_user_2,
            ov_chapter_1.raw_chapter_id,
            schemas.CreateRawChapterRevision(
                raw_chapter_revision_text="Should not work",
                raw_chapter_revision_title="Should not work",
            ),
        )

    # assert admin can create chapters and revisions
    ov_chapter_2 = insert_raw_chapter(
        test_db, p1_admin, ov.novel_id, schemas.CreateRawChapter(raw_chapter_num=2)
    )
    ov_revision_2 = insert_raw_chapter_revision(
        test_db,
        p1_admin,
        ov_chapter_2.raw_chapter_id,
        schemas.CreateRawChapterRevision(
            raw_chapter_revision_text="Admin Text",
            raw_chapter_revision_title="Admin Title",
        ),
    )
    assert ov_chapter_2.raw_chapter_id is not None
    assert ov_revision_2.raw_chapter_revision_id is not None

    # check overall number of revisions
    assert len(test_db.execute(select(RawChapterRevision)).scalars().all()) == 7
