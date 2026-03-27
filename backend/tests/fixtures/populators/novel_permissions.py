"""
Fixtures for novel permission tests.

Creates chapters and revisions on top of the p1_* novel fixtures
from permissions_one.py, covering various visibility and role combinations.
"""

import pytest
from sqlalchemy.orm import Session

from src.novels.models import Chapter, Novel, Revision, RevisionText

# --- Chapters ---

@pytest.fixture
def p1_chapter_public(test_db: Session, p1_novel_public_tyrone: Novel) -> Chapter:
    """Chapter on a PUBLIC novel owned by user_1."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_public_tyrone.novel_id)
    test_db.add(ch)
    test_db.commit()
    return ch


@pytest.fixture
def p1_chapter_restricted(test_db: Session, p1_novel_restricted_tyrone: Novel) -> Chapter:
    """Chapter on a RESTRICTED novel owned by user_1."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_restricted_tyrone.novel_id)
    test_db.add(ch)
    test_db.commit()
    return ch


@pytest.fixture
def p1_chapter_private(test_db: Session, p1_novel_private_tyrone: Novel) -> Chapter:
    """Chapter on a PRIVATE novel owned by user_1 only."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_private_tyrone.novel_id)
    test_db.add(ch)
    test_db.commit()
    return ch


@pytest.fixture
def p1_chapter_owner_editor(test_db: Session, p1_novel_owner_editor: Novel) -> Chapter:
    """Chapter on a PRIVATE novel where user_1=OWNER, user_2=EDITOR."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_owner_editor.novel_id)
    test_db.add(ch)
    test_db.commit()
    return ch


@pytest.fixture
def p1_chapter_owner_viewer(test_db: Session, p1_novel_owner_viewer: Novel) -> Chapter:
    """Chapter on a PRIVATE novel where user_1=OWNER, user_2=VIEWER."""
    ch = Chapter(chapter_num=1, novel_id=p1_novel_owner_viewer.novel_id)
    test_db.add(ch)
    test_db.commit()
    return ch


# --- Revisions ---

@pytest.fixture
def p1_revision_public(test_db: Session, p1_chapter_public: Chapter) -> tuple[Revision, RevisionText]:
    """Public revision on a PUBLIC novel."""
    rev = Revision(
        chapter_id=p1_chapter_public.chapter_id,
        revision_title="Public Ch1",
        revision_is_primary=True,
        revision_is_public=True,
    )
    test_db.add(rev)
    test_db.commit()
    rt = RevisionText(revision_id=rev.revision_id, revision_text_content="Public chapter text.", revision_text_version=1)
    test_db.add(rt)
    test_db.commit()
    return rev, rt


@pytest.fixture
def p1_revision_draft_on_public(test_db: Session, p1_chapter_public: Chapter) -> tuple[Revision, RevisionText]:
    """Non-public draft revision on a PUBLIC novel."""
    rev = Revision(
        chapter_id=p1_chapter_public.chapter_id,
        revision_title="Draft Ch1",
        revision_is_primary=False,
        revision_is_public=False,
    )
    test_db.add(rev)
    test_db.commit()
    rt = RevisionText(revision_id=rev.revision_id, revision_text_content="Draft text on public novel.", revision_text_version=1)
    test_db.add(rt)
    test_db.commit()
    return rev, rt


@pytest.fixture
def p1_revision_restricted(test_db: Session, p1_chapter_restricted: Chapter) -> tuple[Revision, RevisionText]:
    """Public revision on a RESTRICTED novel."""
    rev = Revision(
        chapter_id=p1_chapter_restricted.chapter_id,
        revision_title="Restricted Ch1",
        revision_is_primary=True,
        revision_is_public=True,
    )
    test_db.add(rev)
    test_db.commit()
    rt = RevisionText(revision_id=rev.revision_id, revision_text_content="Restricted novel text.", revision_text_version=1)
    test_db.add(rt)
    test_db.commit()
    return rev, rt


@pytest.fixture
def p1_revision_private(test_db: Session, p1_chapter_private: Chapter) -> tuple[Revision, RevisionText]:
    """Non-public revision on a PRIVATE novel."""
    rev = Revision(
        chapter_id=p1_chapter_private.chapter_id,
        revision_title="Private Ch1",
        revision_is_primary=False,
        revision_is_public=False,
    )
    test_db.add(rev)
    test_db.commit()
    rt = RevisionText(revision_id=rev.revision_id, revision_text_content="Private novel text.", revision_text_version=1)
    test_db.add(rt)
    test_db.commit()
    return rev, rt


@pytest.fixture
def p1_revision_owner_editor(test_db: Session, p1_chapter_owner_editor: Chapter) -> tuple[Revision, RevisionText]:
    """Non-public revision on the owner/editor novel."""
    rev = Revision(
        chapter_id=p1_chapter_owner_editor.chapter_id,
        revision_title="OE Ch1",
        revision_is_primary=False,
        revision_is_public=False,
    )
    test_db.add(rev)
    test_db.commit()
    rt = RevisionText(revision_id=rev.revision_id, revision_text_content="Owner-editor novel text.", revision_text_version=1)
    test_db.add(rt)
    test_db.commit()
    return rev, rt


@pytest.fixture
def p1_revision_owner_viewer(test_db: Session, p1_chapter_owner_viewer: Chapter) -> tuple[Revision, RevisionText]:
    """Non-public revision on the owner/viewer novel."""
    rev = Revision(
        chapter_id=p1_chapter_owner_viewer.chapter_id,
        revision_title="OV Ch1",
        revision_is_primary=False,
        revision_is_public=False,
    )
    test_db.add(rev)
    test_db.commit()
    rt = RevisionText(revision_id=rev.revision_id, revision_text_content="Owner-viewer novel text.", revision_text_version=1)
    test_db.add(rt)
    test_db.commit()
    return rev, rt
