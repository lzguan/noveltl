"""
Pytest fixtures that build complete object graphs as bundle dataclasses.

These fixtures create all the DB rows needed for common test scenarios
in a single fixture parameter, reducing the number of fixtures tests
need to request.
"""

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, NovelContributor, SourceWork
from tests.fixtures.bundles import LabelFixtureBundle, NovelFixtureBundle
from tests.fixtures.password_hash import Hash


@pytest.fixture
def novel_bundle(test_db: Session, no_hash: Hash) -> NovelFixtureBundle:
    """Creates a complete novel setup: user, source work, novel, contributor, chapter, chapter content."""
    # Create language
    lang = Language(language_name="English", language_code="en")
    test_db.add(lang)
    test_db.commit()

    # Create user
    user = User(
        user_name="bundle_user",
        user_hashed_password=no_hash.hash("pass"),
        user_type=UserType.USER,
    )
    test_db.add(user)
    test_db.commit()

    # Create source work
    sw = SourceWork(source_work_title="Bundle Source Work")
    test_db.add(sw)
    test_db.commit()

    # Create novel (public, original)
    novel = Novel(
        novel_title="Bundle Test Novel",
        language_code=lang.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
        source_work_id=sw.source_work_id,
    )
    test_db.add(novel)
    test_db.commit()

    # Add contributor
    contributor = NovelContributor(
        novel_id=novel.novel_id,
        user_id=user.user_id,
        contributor_role=Role.OWNER,
    )
    test_db.add(contributor)
    test_db.commit()

    # Create chapter
    chapter = Chapter(
        novel_id=novel.novel_id,
        chapter_num=1,
        chapter_title="Bundle Chapter 1",
        chapter_is_public=True,
    )
    test_db.add(chapter)
    test_db.commit()

    # Create chapter content
    cc = ChapterContent(
        chapter_id=chapter.chapter_id,
        chapter_content_text="Hello world. This is a test sentence.",
        chapter_content_version=1,
    )
    test_db.add(cc)
    test_db.commit()

    return NovelFixtureBundle(
        user=user,
        source_work=sw,
        novel=novel,
        contributor=contributor,
        chapter=chapter,
        chapter_content=cc,
    )


@pytest.fixture
def label_bundle(test_db: Session, novel_bundle: NovelFixtureBundle) -> LabelFixtureBundle:
    """Creates a label group with labels on top of a novel bundle."""
    # Create label group
    group = LabelGroup(
        label_group_name="Bundle Label Group",
        novel_id=novel_bundle.novel.novel_id,
    )
    test_db.add(group)
    test_db.commit()

    # Add label contributor
    lc = LabelContributor(
        label_group_id=group.label_group_id,
        user_id=novel_bundle.user.user_id,
        label_contributor_role=LabelRole.OWNER,
    )
    test_db.add(lc)
    test_db.commit()

    # Create label data
    ld = LabelData(
        label_group_id=group.label_group_id,
        chapter_content_id=novel_bundle.chapter_content.chapter_content_id,
    )
    test_db.add(ld)
    test_db.commit()

    # Create labels matching the chapter content text "Hello world. This is a test sentence."
    labels = [
        Label(
            label_data_id=ld.label_data_id,
            label_entity_group="PER",
            label_word="Hello",
            label_start=0,
            label_end=5,
            label_score=0.9,
            label_dirty=False,
        ),
        Label(
            label_data_id=ld.label_data_id,
            label_entity_group="LOC",
            label_word="world",
            label_start=6,
            label_end=11,
            label_score=0.5,
            label_dirty=False,
        ),
        Label(
            label_data_id=ld.label_data_id,
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

    return LabelFixtureBundle(
        novel=novel_bundle,
        label_group=group,
        label_contributor=lc,
        label_data=ld,
        labels=labels,
    )
