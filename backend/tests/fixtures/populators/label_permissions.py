"""
Fixtures for testing label permissions.

Sets up:
- 2 users (lp_user_1, lp_user_2) + 1 admin
- 1 public novel owned by user_1 with chapters/revisions
- Label groups with various contributor configurations
- Label data and labels for testing

Note: this test is AI generated.
"""

from typing import Any, Protocol

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Chapter, Contributor, Novel, Revision, RevisionText


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...
    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


# --- Language ---
@pytest.fixture
def lp_language(test_db: Session) -> Language:
    lang = Language(language_name="English", language_code="en")
    test_db.add(lang)
    test_db.commit()
    return lang


# --- Users ---
@pytest.fixture
def lp_user_1(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="lp_alice", user_hashed_password=no_hash.hash("pass1"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def lp_user_2(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="lp_bob", user_hashed_password=no_hash.hash("pass2"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def lp_user_3(test_db: Session, no_hash: Hash) -> User:
    """A third user who is not a contributor to any label group."""
    user = User(user_name="lp_charlie", user_hashed_password=no_hash.hash("pass3"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def lp_admin(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="lp_admin", user_hashed_password=no_hash.hash("adminpass"), user_type=UserType.ADMIN)
    test_db.add(user)
    test_db.commit()
    return user


# --- Novels ---
@pytest.fixture
def lp_novel_public(test_db: Session, lp_language: Language, lp_user_1: User) -> Novel:
    novel = Novel(
        novel_title="LP Public Novel",
        language_code=lp_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=lp_user_1.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def lp_novel_private(test_db: Session, lp_language: Language, lp_user_1: User) -> Novel:
    novel = Novel(
        novel_title="LP Private Novel",
        language_code=lp_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PRIVATE,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=lp_user_1.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


# --- Chapters/Revisions ---
@pytest.fixture
def lp_chapter_public(test_db: Session, lp_novel_public: Novel) -> tuple[Chapter, Revision, RevisionText]:
    chapter = Chapter(chapter_num=1, novel_id=lp_novel_public.novel_id)
    test_db.add(chapter)
    test_db.commit()
    revision = Revision(
        revision_title="Chapter 1", revision_is_primary=True, revision_is_public=True, chapter_id=chapter.chapter_id
    )
    test_db.add(revision)
    test_db.commit()
    rt = RevisionText(
        revision_id=revision.revision_id,
        revision_text_content="This is test content for the public novel chapter.",
        revision_text_version=1,
    )
    test_db.add(rt)
    test_db.commit()
    return chapter, revision, rt


@pytest.fixture
def lp_chapter_private(test_db: Session, lp_novel_private: Novel) -> tuple[Chapter, Revision, RevisionText]:
    chapter = Chapter(chapter_num=1, novel_id=lp_novel_private.novel_id)
    test_db.add(chapter)
    test_db.commit()
    revision = Revision(
        revision_title="Chapter 1", revision_is_primary=False, revision_is_public=False, chapter_id=chapter.chapter_id
    )
    test_db.add(revision)
    test_db.commit()
    rt = RevisionText(
        revision_id=revision.revision_id,
        revision_text_content="This is test content for the private novel chapter.",
        revision_text_version=1,
    )
    test_db.add(rt)
    test_db.commit()
    return chapter, revision, rt


# --- Label Groups ---
@pytest.fixture
def lp_label_group_owner_only(test_db: Session, lp_novel_public: Novel, lp_user_1: User) -> LabelGroup:
    """Label group where only user_1 is OWNER."""
    lg = LabelGroup(label_group_name="Owner Only Group", novel_id=lp_novel_public.novel_id)
    test_db.add(lg)
    test_db.commit()
    test_db.add(
        LabelContributor(
            label_group_id=lg.label_group_id, user_id=lp_user_1.user_id, label_contributor_role=LabelRole.OWNER
        )
    )
    test_db.commit()
    return lg


@pytest.fixture
def lp_label_group_with_editor(
    test_db: Session, lp_novel_public: Novel, lp_user_1: User, lp_user_2: User
) -> LabelGroup:
    """Label group where user_1 is OWNER, user_2 is EDITOR."""
    lg = LabelGroup(label_group_name="With Editor Group", novel_id=lp_novel_public.novel_id)
    test_db.add(lg)
    test_db.commit()
    test_db.add(
        LabelContributor(
            label_group_id=lg.label_group_id, user_id=lp_user_1.user_id, label_contributor_role=LabelRole.OWNER
        )
    )
    test_db.add(
        LabelContributor(
            label_group_id=lg.label_group_id, user_id=lp_user_2.user_id, label_contributor_role=LabelRole.EDITOR
        )
    )
    test_db.commit()
    return lg


@pytest.fixture
def lp_label_group_with_viewer(
    test_db: Session, lp_novel_public: Novel, lp_user_1: User, lp_user_2: User
) -> LabelGroup:
    """Label group where user_1 is OWNER, user_2 is VIEWER."""
    lg = LabelGroup(label_group_name="With Viewer Group", novel_id=lp_novel_public.novel_id)
    test_db.add(lg)
    test_db.commit()
    test_db.add(
        LabelContributor(
            label_group_id=lg.label_group_id, user_id=lp_user_1.user_id, label_contributor_role=LabelRole.OWNER
        )
    )
    test_db.add(
        LabelContributor(
            label_group_id=lg.label_group_id, user_id=lp_user_2.user_id, label_contributor_role=LabelRole.VIEWER
        )
    )
    test_db.commit()
    return lg


@pytest.fixture
def lp_label_group_private_novel(test_db: Session, lp_novel_private: Novel, lp_user_1: User) -> LabelGroup:
    """Label group on a private novel, user_1 is OWNER."""
    lg = LabelGroup(label_group_name="Private Novel Group", novel_id=lp_novel_private.novel_id)
    test_db.add(lg)
    test_db.commit()
    test_db.add(
        LabelContributor(
            label_group_id=lg.label_group_id, user_id=lp_user_1.user_id, label_contributor_role=LabelRole.OWNER
        )
    )
    test_db.commit()
    return lg


# --- Label Data ---
@pytest.fixture
def lp_label_data_owner_only(
    test_db: Session, lp_label_group_owner_only: LabelGroup, lp_chapter_public: tuple[Chapter, Revision, RevisionText]
) -> LabelData:
    _, _, rt = lp_chapter_public
    ld = LabelData(label_group_id=lp_label_group_owner_only.label_group_id, revision_text_id=rt.revision_text_id)
    test_db.add(ld)
    test_db.commit()
    return ld


@pytest.fixture
def lp_label_data_with_editor(
    test_db: Session, lp_label_group_with_editor: LabelGroup, lp_chapter_public: tuple[Chapter, Revision, RevisionText]
) -> LabelData:
    _, _, rt = lp_chapter_public
    ld = LabelData(label_group_id=lp_label_group_with_editor.label_group_id, revision_text_id=rt.revision_text_id)
    test_db.add(ld)
    test_db.commit()
    return ld


@pytest.fixture
def lp_label_data_with_viewer(
    test_db: Session, lp_label_group_with_viewer: LabelGroup, lp_chapter_public: tuple[Chapter, Revision, RevisionText]
) -> LabelData:
    _, _, rt = lp_chapter_public
    ld = LabelData(label_group_id=lp_label_group_with_viewer.label_group_id, revision_text_id=rt.revision_text_id)
    test_db.add(ld)
    test_db.commit()
    return ld


@pytest.fixture
def lp_label_data_private_novel(
    test_db: Session,
    lp_label_group_private_novel: LabelGroup,
    lp_chapter_private: tuple[Chapter, Revision, RevisionText],
) -> LabelData:
    _, _, rt = lp_chapter_private
    ld = LabelData(label_group_id=lp_label_group_private_novel.label_group_id, revision_text_id=rt.revision_text_id)
    test_db.add(ld)
    test_db.commit()
    return ld


# --- Labels ---
@pytest.fixture
def lp_labels_owner_only(test_db: Session, lp_label_data_owner_only: LabelData) -> list[Label]:
    """Labels in the owner-only group. Text: 'This is test content for the public novel chapter.'"""
    labels = [
        Label(
            label_data_id=lp_label_data_owner_only.label_data_id,
            label_word="test",
            label_start=8,
            label_end=12,
            label_entity_group="MISC",
            label_score=0.95,
            label_dirty=False,
        ),
        Label(
            label_data_id=lp_label_data_owner_only.label_data_id,
            label_word="content",
            label_start=13,
            label_end=20,
            label_entity_group="MISC",
            label_score=0.90,
            label_dirty=False,
        ),
    ]
    test_db.add_all(labels)
    test_db.commit()
    return labels


@pytest.fixture
def lp_labels_with_editor(test_db: Session, lp_label_data_with_editor: LabelData) -> list[Label]:
    """Labels in the editor group."""
    labels = [
        Label(
            label_data_id=lp_label_data_with_editor.label_data_id,
            label_word="test",
            label_start=8,
            label_end=12,
            label_entity_group="MISC",
            label_score=0.95,
            label_dirty=False,
        ),
    ]
    test_db.add_all(labels)
    test_db.commit()
    return labels


@pytest.fixture
def lp_labels_with_viewer(test_db: Session, lp_label_data_with_viewer: LabelData) -> list[Label]:
    """Labels in the viewer group."""
    labels = [
        Label(
            label_data_id=lp_label_data_with_viewer.label_data_id,
            label_word="test",
            label_start=8,
            label_end=12,
            label_entity_group="MISC",
            label_score=0.95,
            label_dirty=False,
        ),
    ]
    test_db.add_all(labels)
    test_db.commit()
    return labels
