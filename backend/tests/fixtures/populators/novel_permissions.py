"""
Fixtures for novel permission tests.

Creates chapters and chapter contents on top of the p1_* novel fixtures
from permissions_one.py, covering various visibility and role combinations.
"""

import pytest
from sqlalchemy.orm import Session

from src.novels.models import Chapter, ChapterContent, Novel

# --- Chapters ---

@pytest.fixture
def p1_chapter_public(test_db: Session, p1_novel_public_tyrone: Novel) -> Chapter:
    """Public chapter on a PUBLIC novel owned by user_1."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_public_tyrone.novel_id, chapter_title="Public Ch1", chapter_is_public=True)
    test_db.add(ch)
    test_db.commit()
    return ch


@pytest.fixture
def p1_chapter_restricted(test_db: Session, p1_novel_restricted_tyrone: Novel) -> Chapter:
    """Public chapter on a RESTRICTED novel owned by user_1."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_restricted_tyrone.novel_id, chapter_title="Restricted Ch1", chapter_is_public=True)
    test_db.add(ch)
    test_db.commit()
    return ch


@pytest.fixture
def p1_chapter_private(test_db: Session, p1_novel_private_tyrone: Novel) -> Chapter:
    """Non-public chapter on a PRIVATE novel owned by user_1 only."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_private_tyrone.novel_id, chapter_title="Private Ch1", chapter_is_public=False)
    test_db.add(ch)
    test_db.commit()
    return ch


@pytest.fixture
def p1_chapter_owner_editor(test_db: Session, p1_novel_owner_editor: Novel) -> Chapter:
    """Non-public chapter on a PRIVATE novel where user_1=OWNER, user_2=EDITOR."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_owner_editor.novel_id, chapter_title="OE Ch1", chapter_is_public=False)
    test_db.add(ch)
    test_db.commit()
    return ch


@pytest.fixture
def p1_chapter_owner_viewer(test_db: Session, p1_novel_owner_viewer: Novel) -> Chapter:
    """Non-public chapter on a PRIVATE novel where user_1=OWNER, user_2=VIEWER."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_owner_viewer.novel_id, chapter_title="OV Ch1", chapter_is_public=False)
    test_db.add(ch)
    test_db.commit()
    return ch


# --- Chapter Contents ---

@pytest.fixture
def p1_chapter_content_public(test_db: Session, p1_chapter_public: Chapter) -> ChapterContent:
    """Chapter content on a PUBLIC novel."""
    cc = ChapterContent(chapter_id=p1_chapter_public.chapter_id, chapter_content_text="Public chapter text.", chapter_content_version=1)
    test_db.add(cc)
    test_db.commit()
    return cc


@pytest.fixture
def p1_chapter_content_draft_on_public(test_db: Session, p1_chapter_public: Chapter) -> ChapterContent:
    """Second version of chapter content on a PUBLIC novel (draft)."""
    cc = ChapterContent(chapter_id=p1_chapter_public.chapter_id, chapter_content_text="Draft text on public novel.", chapter_content_version=2)
    test_db.add(cc)
    test_db.commit()
    return cc


@pytest.fixture
def p1_chapter_content_restricted(test_db: Session, p1_chapter_restricted: Chapter) -> ChapterContent:
    """Chapter content on a RESTRICTED novel."""
    cc = ChapterContent(chapter_id=p1_chapter_restricted.chapter_id, chapter_content_text="Restricted novel text.", chapter_content_version=1)
    test_db.add(cc)
    test_db.commit()
    return cc


@pytest.fixture
def p1_chapter_content_private(test_db: Session, p1_chapter_private: Chapter) -> ChapterContent:
    """Chapter content on a PRIVATE novel."""
    cc = ChapterContent(chapter_id=p1_chapter_private.chapter_id, chapter_content_text="Private novel text.", chapter_content_version=1)
    test_db.add(cc)
    test_db.commit()
    return cc


@pytest.fixture
def p1_chapter_content_owner_editor(test_db: Session, p1_chapter_owner_editor: Chapter) -> ChapterContent:
    """Chapter content on the owner/editor novel."""
    cc = ChapterContent(chapter_id=p1_chapter_owner_editor.chapter_id, chapter_content_text="Owner-editor novel text.", chapter_content_version=1)
    test_db.add(cc)
    test_db.commit()
    return cc


@pytest.fixture
def p1_chapter_content_owner_viewer(test_db: Session, p1_chapter_owner_viewer: Chapter) -> ChapterContent:
    """Chapter content on the owner/viewer novel."""
    cc = ChapterContent(chapter_id=p1_chapter_owner_viewer.chapter_id, chapter_content_text="Owner-viewer novel text.", chapter_content_version=1)
    test_db.add(cc)
    test_db.commit()
    return cc
