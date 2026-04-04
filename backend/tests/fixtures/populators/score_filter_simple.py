"""
Fixtures for testing ScoreFilter. Sets up a novel with one chapter and three labels with varying scores.

Note: These fixtures are AI generated.
"""

from typing import Any, Protocol

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...
    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


@pytest.fixture
def sf_language(test_db: Session) -> Language:
    lang = Language(language_name="English", language_code="en")
    test_db.add(lang)
    test_db.commit()
    return lang


@pytest.fixture
def sf_user(test_db: Session, no_hash : Hash) -> User:
    from src.auth.constants import UserType
    user = User(user_name="sf_user", user_hashed_password=no_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sf_source_work(test_db: Session) -> SourceWork:
    sw = SourceWork(source_work_title="SF Source Work")
    test_db.add(sw)
    test_db.commit()
    return sw


@pytest.fixture
def sf_novel(test_db: Session, sf_language: Language, sf_user: User, sf_source_work: SourceWork) -> Novel:
    novel = Novel(
        novel_title="SF Test Novel",
        language_code=sf_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
        source_work_id=sf_source_work.source_work_id
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(NovelContributor(novel_id=novel.novel_id, user_id=sf_user.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def sf_chapter(test_db: Session, sf_novel: Novel) -> Chapter:
    chapter = Chapter(novel_id=sf_novel.novel_id, chapter_num=1, chapter_title="Test Chapter", chapter_is_public=True)
    test_db.add(chapter)
    test_db.commit()
    return chapter


@pytest.fixture
def sf_chapter_content(test_db: Session, sf_chapter: Chapter) -> ChapterContent:
    cc = ChapterContent(
        chapter_id=sf_chapter.chapter_id,
        chapter_content_text="Hello world. This is a test sentence. Another sentence here.",
        chapter_content_version=1
    )
    test_db.add(cc)
    test_db.commit()
    return cc


@pytest.fixture
def sf_label_group(test_db: Session, sf_novel: Novel, sf_user: User) -> LabelGroup:
    group = LabelGroup(
        label_group_name="SF Test Group",
        novel_id=sf_novel.novel_id
    )
    test_db.add(group)
    test_db.commit()
    test_db.add(LabelContributor(
        label_group_id=group.label_group_id,
        user_id=sf_user.user_id,
        label_contributor_role=LabelRole.OWNER
    ))
    test_db.commit()
    return group


@pytest.fixture
def sf_label_data(test_db: Session, sf_label_group: LabelGroup, sf_chapter_content: ChapterContent) -> LabelData:
    label_data = LabelData(
        label_group_id=sf_label_group.label_group_id,
        chapter_content_id=sf_chapter_content.chapter_content_id
    )
    test_db.add(label_data)
    test_db.commit()
    return label_data


@pytest.fixture
def sf_labels(test_db: Session, sf_label_data: LabelData) -> list[Label]:
    """Creates labels with varying scores for testing."""
    labels = [
        Label(
            label_data_id=sf_label_data.label_data_id,
            label_entity_group="MISC",
            label_word="Hello",
            label_start=0,
            label_end=5,
            label_score=0.9,
            label_dirty=False
        ),
        Label(
            label_data_id=sf_label_data.label_data_id,
            label_entity_group="MISC",
            label_word="world",
            label_start=6,
            label_end=11,
            label_score=0.5,
            label_dirty=False
        ),
        Label(
            label_data_id=sf_label_data.label_data_id,
            label_entity_group="MISC",
            label_word="test",
            label_start=22,
            label_end=26,
            label_score=0.3,
            label_dirty=False
        ),
    ]
    test_db.add_all(labels)
    test_db.commit()
    return labels
