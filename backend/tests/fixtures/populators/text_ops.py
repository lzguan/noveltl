"""
Fixtures for testing modify_revision_text and text operations.

Sets up a novel with one chapter, one revision, one revision text,
and two label groups each with their own labels. This allows testing
that label porting works across multiple label groups.

Text content: "Hello world. This is a test sentence."
Labels group 1: "Hello" [0,5), "world" [6,11), "test" [22,26)
Labels group 2: "sentence" [27,35)
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


TEXT_CONTENT = "Hello world. This is a test sentence."


@pytest.fixture
def to_language(test_db: Session) -> Language:
    lang = Language(language_name="English", language_code="en")
    test_db.add(lang)
    test_db.commit()
    return lang


@pytest.fixture
def to_user(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="to_user", user_hashed_password=no_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def to_other_user(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="to_other", user_hashed_password=no_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def to_admin(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="to_admin", user_hashed_password=no_hash.hash("pass"), user_type=UserType.ADMIN)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def to_novel(test_db: Session, to_language: Language, to_user: User) -> Novel:
    novel = Novel(
        novel_title="TextOps Test Novel",
        language_code=to_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=to_user.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def to_chapter(test_db: Session, to_novel: Novel) -> Chapter:
    chapter = Chapter(novel_id=to_novel.novel_id, chapter_num=1)
    test_db.add(chapter)
    test_db.commit()
    return chapter


@pytest.fixture
def to_revision(test_db: Session, to_chapter: Chapter) -> Revision:
    revision = Revision(
        chapter_id=to_chapter.chapter_id,
        revision_title="Test Chapter",
        revision_is_public=True,
        revision_is_primary=True,
    )
    test_db.add(revision)
    test_db.commit()
    return revision


@pytest.fixture
def to_revision_text(test_db: Session, to_revision: Revision) -> RevisionText:
    rt = RevisionText(
        revision_id=to_revision.revision_id,
        revision_text_content=TEXT_CONTENT,
        revision_text_version=1,
    )
    test_db.add(rt)
    test_db.commit()
    return rt


# --- Label group 1: three labels ---

@pytest.fixture
def to_label_group_1(test_db: Session, to_novel: Novel, to_user: User) -> LabelGroup:
    group = LabelGroup(label_group_name="Group 1", novel_id=to_novel.novel_id)
    test_db.add(group)
    test_db.commit()
    test_db.add(LabelContributor(
        label_group_id=group.label_group_id,
        user_id=to_user.user_id,
        label_contributor_role=LabelRole.OWNER,
    ))
    test_db.commit()
    return group


@pytest.fixture
def to_label_data_1(test_db: Session, to_label_group_1: LabelGroup, to_revision_text: RevisionText) -> LabelData:
    ld = LabelData(label_group_id=to_label_group_1.label_group_id, revision_text_id=to_revision_text.revision_text_id)
    test_db.add(ld)
    test_db.commit()
    return ld


@pytest.fixture
def to_labels_1(test_db: Session, to_label_data_1: LabelData) -> list[Label]:
    labels = [
        Label(
            label_data_id=to_label_data_1.label_data_id,
            label_entity_group="PER",
            label_word="Hello",
            label_start=0,
            label_end=5,
            label_score=0.9,
            label_dirty=False,
        ),
        Label(
            label_data_id=to_label_data_1.label_data_id,
            label_entity_group="LOC",
            label_word="world",
            label_start=6,
            label_end=11,
            label_score=0.5,
            label_dirty=False,
        ),
        Label(
            label_data_id=to_label_data_1.label_data_id,
            label_entity_group="MISC",
            label_word="test",
            label_start=22,
            label_end=26,
            label_score=0.3,
            label_dirty=False,
        ),
    ]
    test_db.add_all(labels)
    test_db.commit()
    return labels


# --- Label group 2: one label ---

@pytest.fixture
def to_label_group_2(test_db: Session, to_novel: Novel, to_user: User) -> LabelGroup:
    group = LabelGroup(label_group_name="Group 2", novel_id=to_novel.novel_id)
    test_db.add(group)
    test_db.commit()
    test_db.add(LabelContributor(
        label_group_id=group.label_group_id,
        user_id=to_user.user_id,
        label_contributor_role=LabelRole.OWNER,
    ))
    test_db.commit()
    return group


@pytest.fixture
def to_label_data_2(test_db: Session, to_label_group_2: LabelGroup, to_revision_text: RevisionText) -> LabelData:
    ld = LabelData(label_group_id=to_label_group_2.label_group_id, revision_text_id=to_revision_text.revision_text_id)
    test_db.add(ld)
    test_db.commit()
    return ld


@pytest.fixture
def to_labels_2(test_db: Session, to_label_data_2: LabelData) -> list[Label]:
    labels = [
        Label(
            label_data_id=to_label_data_2.label_data_id,
            label_entity_group="MISC",
            label_word="sentence",
            label_start=27,
            label_end=35,
            label_score=0.8,
            label_dirty=False,
        ),
    ]
    test_db.add_all(labels)
    test_db.commit()
    return labels
