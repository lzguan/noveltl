from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.languages.models import Language
from src.memory.access import MemAccessContext, write_memory
from src.memory.models import MemoryGroup
from src.memory.plugins.glossary.access import contains_query, create_memory, create_term
from src.memory.plugins.glossary.models import GlossaryAssociation
from src.memory.plugins.glossary.service import query_glossary_terms, query_memories_for_term
from src.memory.types import Creator, MemoryType, Scope
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork


@dataclass(frozen=True)
class GlossaryQueryScenario:
    admin: User
    chapter: Chapter
    memory_group: MemoryGroup
    alpha_term_id: UUID


def _seed_glossary_query_scenario(db: Session) -> GlossaryQueryScenario:
    admin = User(
        user_name="glossary-query-admin",
        user_hashed_password="not-used",
        user_type=UserType.ADMIN,
    )
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Glossary query source")
    db.add_all([admin, language, source_work])
    db.flush()

    novel = Novel(
        novel_title="Glossary query novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    db.add(novel)
    db.flush()

    first_chapter = Chapter(
        chapter_num=1,
        chapter_title="Chapter 1",
        chapter_is_public=False,
        novel_id=novel.novel_id,
    )
    current_chapter = Chapter(
        chapter_num=2,
        chapter_title="Chapter 2",
        chapter_is_public=False,
        novel_id=novel.novel_id,
    )
    db.add_all([first_chapter, current_chapter])
    db.flush()

    first_content = ChapterContent(
        chapter_content_text="Alpha and Gamma",
        chapter_content_version=1,
        chapter_id=first_chapter.chapter_id,
    )
    outdated_current_content = ChapterContent(
        chapter_content_text="OldOnly",
        chapter_content_version=1,
        chapter_id=current_chapter.chapter_id,
    )
    latest_current_content = ChapterContent(
        chapter_content_text="《Alpha》 and Beta",
        chapter_content_version=2,
        chapter_id=current_chapter.chapter_id,
    )
    memory_group = MemoryGroup(
        memory_group_name="Glossary query group",
        novel_id=novel.novel_id,
        memory_language=language.language_code,
    )
    db.add_all([first_content, outdated_current_content, latest_current_content, memory_group])
    db.flush()

    terms = {
        term: create_term(db, memory_group.memory_group_id, term)
        for term in ["Alpha", "Beta", "Gamma", "OldOnly"]
    }

    first_context = MemAccessContext(
        memory_group_id=memory_group.memory_group_id,
        chapter_id=first_chapter.chapter_id,
        chapter_content_id=first_content.chapter_content_id,
    )
    create_memory(
        db,
        first_context,
        Creator.AGENT,
        MemoryType.FACT,
        ["Alpha"],
        "Alpha has one persistent memory.",
        Scope.PERSIST,
    )
    create_memory(
        db,
        first_context,
        Creator.AGENT,
        MemoryType.FACT,
        ["Alpha"],
        "Alpha has one expired local memory.",
        Scope.LOCAL,
    )
    for index in range(3):
        create_memory(
            db,
            first_context,
            Creator.AGENT,
            MemoryType.FACT,
            ["Gamma"],
            f"Gamma memory {index}.",
            Scope.PERSIST,
        )

    other_plugin_memory = write_memory(
        db,
        first_context,
        MemoryType.FACT,
        "This association must not affect glossary counts.",
        Creator.AGENT,
        "other",
        Scope.PERSIST,
    )
    db.add(GlossaryAssociation(term_id=terms["Alpha"].term_id, memory_id=other_plugin_memory.memory_id))
    db.commit()
    return GlossaryQueryScenario(
        admin=admin,
        chapter=current_chapter,
        memory_group=memory_group,
        alpha_term_id=terms["Alpha"].term_id,
    )


def test_glossary_terms_are_ordered_by_all_associated_glossary_memories(test_db: Session) -> None:
    scenario = _seed_glossary_query_scenario(test_db)

    page = query_glossary_terms(
        test_db,
        scenario.admin,
        scenario.memory_group.memory_group_id,
        contains_query,
        skip=0,
        limit=10,
    )

    assert page.count == 4
    assert [(row.term, row.associated_memory_count) for row in page.rows] == [
        ("Gamma", 3),
        ("Alpha", 2),
        ("Beta", 0),
        ("OldOnly", 0),
    ]


def test_chapter_scoped_terms_use_latest_content_and_active_memory_counts(test_db: Session) -> None:
    scenario = _seed_glossary_query_scenario(test_db)

    page = query_glossary_terms(
        test_db,
        scenario.admin,
        scenario.memory_group.memory_group_id,
        contains_query,
        skip=0,
        limit=10,
        chapter_id=scenario.chapter.chapter_id,
    )

    assert page.count == 2
    assert [(row.term, row.associated_memory_count) for row in page.rows] == [
        ("Alpha", 1),
        ("Beta", 0),
    ]


def test_glossary_term_search_and_pagination_apply_after_count_ordering(test_db: Session) -> None:
    scenario = _seed_glossary_query_scenario(test_db)

    page = query_glossary_terms(
        test_db,
        scenario.admin,
        scenario.memory_group.memory_group_id,
        contains_query,
        skip=1,
        limit=2,
        search="a",
    )

    assert page.count == 3
    assert [(row.term, row.associated_memory_count) for row in page.rows] == [
        ("Alpha", 2),
        ("Beta", 0),
    ]


def test_memories_for_term_can_be_scoped_to_active_memories_at_a_chapter(
    test_db: Session,
) -> None:
    scenario = _seed_glossary_query_scenario(test_db)

    all_memories = query_memories_for_term(
        test_db,
        scenario.admin,
        scenario.memory_group.memory_group_id,
        scenario.alpha_term_id,
    )
    active_memories = query_memories_for_term(
        test_db,
        scenario.admin,
        scenario.memory_group.memory_group_id,
        scenario.alpha_term_id,
        chapter_id=scenario.chapter.chapter_id,
    )

    assert all_memories.count == 2
    assert active_memories.count == 1
    assert [row.memory.memory_content for row in active_memories.rows] == [
        "Alpha has one persistent memory."
    ]
