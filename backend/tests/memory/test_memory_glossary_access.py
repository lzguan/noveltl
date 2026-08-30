import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.languages.models import Language
from src.memory.access import MemAccessContext, write_memory
from src.memory.exceptions import MemoryNotFoundException
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.glossary.access import (
    GLOSSARY_PLUGIN_NAME,
    create_memory,
    create_term,
    inspect_terms,
    supersede_memory,
)
from src.memory.plugins.glossary.access import (
    expire_memory as expire_glossary_memory,
)
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.glossary.service import delete_glossary_term
from src.memory.plugins.glossary.types import TermKind
from src.memory.service import delete_memory, expire_memory, update_memory
from src.memory.types import Creator, MemoryType, Scope
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork


def test_glossary_access_filters_memory_types_and_plugin_ownership(test_db: Session) -> None:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Memory test source")
    test_db.add_all([language, source_work])
    test_db.flush()

    novel = Novel(
        novel_title="Memory test novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    test_db.add(novel)
    test_db.flush()

    chapter = Chapter(chapter_num=1, chapter_title="Chapter 1", chapter_is_public=False, novel_id=novel.novel_id)
    test_db.add(chapter)
    test_db.flush()

    chapter_content = ChapterContent(
        chapter_content_text="Alpha and Beta",
        chapter_content_version=1,
        chapter_id=chapter.chapter_id,
    )
    next_chapter = Chapter(chapter_num=2, chapter_title="Chapter 2", chapter_is_public=False, novel_id=novel.novel_id)
    test_db.add(next_chapter)
    test_db.flush()
    next_chapter_content = ChapterContent(
        chapter_content_text="Alpha returns",
        chapter_content_version=1,
        chapter_id=next_chapter.chapter_id,
    )
    memory_group = MemoryGroup(
        memory_group_name="Memory test group",
        novel_id=novel.novel_id,
        memory_language=language.language_code,
    )
    test_db.add_all([chapter_content, next_chapter_content, memory_group])
    test_db.flush()

    alpha = create_term(test_db, memory_group.memory_group_id, "Alpha", TermKind.PERSON)
    create_term(test_db, memory_group.memory_group_id, "Beta")
    assert alpha.term_kind == TermKind.PERSON
    context = MemAccessContext(
        memory_group_id=memory_group.memory_group_id,
        chapter_id=chapter.chapter_id,
        chapter_content_id=chapter_content.chapter_content_id,
    )
    fact, _ = create_memory(
        test_db,
        context,
        Creator.AGENT,
        MemoryType.FACT,
        ["Alpha"],
        "Alpha has a durable property.",
        mark="trait",
    )
    relation, _ = create_memory(
        test_db,
        context,
        Creator.AGENT,
        MemoryType.RELATION,
        ["Alpha", "Beta"],
        "Alpha is related to Beta.",
        mark="friendship",
    )
    event, _ = create_memory(
        test_db,
        context,
        Creator.AGENT,
        MemoryType.EVENT,
        ["Alpha", "Beta"],
        "Alpha briefly encountered Beta.",
        Scope.LOCAL,
    )
    other_plugin_memory = write_memory(
        test_db,
        context,
        MemoryType.FACT,
        "Alpha has data owned by another plugin.",
        Creator.AGENT,
        "other",
    )
    test_db.add(GlossaryAssociation(term_id=alpha.term_id, memory_id=other_plugin_memory.memory_id))
    test_db.commit()

    assert fact.plugin_name == GLOSSARY_PLUGIN_NAME
    assert fact.mark == "trait"
    assert relation.plugin_name == GLOSSARY_PLUGIN_NAME
    assert relation.mark == "friendship"

    fact_page = inspect_terms(test_db, context, ["Alpha"], [MemoryType.FACT])
    assert fact_page.count == 1
    assert [item.memory.memory_id for item in fact_page.rows] == [
        fact.memory_id
    ]
    relation_page = inspect_terms(test_db, context, ["Alpha"], [MemoryType.RELATION])
    assert relation_page.count == 1
    assert [item.memory.memory_id for item in relation_page.rows] == [
        relation.memory_id
    ]
    first_page = inspect_terms(test_db, context, ["Alpha"], None, limit=1)
    second_page = inspect_terms(test_db, context, ["Alpha"], None, skip=1, limit=1)
    assert first_page.count == 3
    assert second_page.count == 3
    assert len(first_page.rows) == len(second_page.rows) == 1
    assert first_page.rows[0].memory.memory_id != second_page.rows[0].memory.memory_id
    assert inspect_terms(test_db, context, ["Alpha"], []).model_dump() == {"count": 0, "rows": []}

    marked_page = inspect_terms(
        test_db,
        context,
        ["Alpha"],
        None,
        limit=1,
        marks=["trait"],
    )
    assert marked_page.count == 1
    assert [item.memory.memory_id for item in marked_page.rows] == [fact.memory_id]
    unmarked_page = inspect_terms(test_db, context, ["Alpha"], None, marks=[None])
    assert {item.memory.memory_id for item in unmarked_page.rows} == {event.memory_id}
    mixed_mark_page = inspect_terms(test_db, context, ["Alpha"], None, marks=[None, "trait"])
    assert {item.memory.memory_id for item in mixed_mark_page.rows} == {event.memory_id, fact.memory_id}
    searched_page = inspect_terms(
        test_db,
        context,
        ["Alpha"],
        None,
        term_search="DURABLE",
    )
    assert searched_page.count == 1
    assert [item.memory.memory_id for item in searched_page.rows] == [fact.memory_id]
    assert inspect_terms(test_db, context, ["Alpha"], None, term_search="%").count == 0
    assert inspect_terms(test_db, context, ["Alpha"], None, term_search="_").count == 0
    combined_page = inspect_terms(
        test_db,
        context,
        ["Alpha"],
        None,
        marks=["friendship"],
        term_search="related to beta",
    )
    assert combined_page.count == 1
    assert [item.memory.memory_id for item in combined_page.rows] == [relation.memory_id]
    assert inspect_terms(test_db, context, ["Alpha"], None, marks=[]).count == 0

    event_page = inspect_terms(test_db, context, ["Alpha"], [MemoryType.EVENT])
    assert event_page.count == 1
    assert len(event_page.rows[0].terms) == 2

    next_context = MemAccessContext(
        memory_group_id=memory_group.memory_group_id,
        chapter_id=next_chapter.chapter_id,
        chapter_content_id=next_chapter_content.chapter_content_id,
    )
    assert inspect_terms(test_db, next_context, ["Alpha"], [MemoryType.EVENT]).count == 0
    historical_events = inspect_terms(
        test_db,
        next_context,
        ["Alpha"],
        [MemoryType.EVENT],
        active_only=False,
    )
    assert historical_events.count == 1
    assert [item.memory.memory_id for item in historical_events.rows] == [event.memory_id]

    successor, _ = supersede_memory(
        test_db,
        next_context,
        fact.memory_id,
        Creator.AGENT,
        MemoryType.FACT,
        "Alpha has a replacement property.",
        mark="ability",
    )
    assert successor.mark == "ability"
    successor_page = inspect_terms(
        test_db,
        next_context,
        ["Alpha"],
        [MemoryType.FACT],
        marks=["ability"],
    )
    assert [item.memory.memory_id for item in successor_page.rows] == [successor.memory_id]

    all_memories = inspect_terms(test_db, context, ["Alpha"], None)
    assert {item.memory.memory_id for item in all_memories.rows} == {
        fact.memory_id,
        relation.memory_id,
        event.memory_id,
    }
    with pytest.raises(MemoryNotFoundException):
        supersede_memory(
            test_db,
            next_context,
            other_plugin_memory.memory_id,
            Creator.AGENT,
            MemoryType.FACT,
            "Glossary must not supersede this memory.",
        )
    with pytest.raises(MemoryNotFoundException):
        expire_glossary_memory(
            test_db,
            next_context,
            other_plugin_memory.memory_id,
            [MemoryType.FACT],
        )

    test_db.refresh(other_plugin_memory)
    assert other_plugin_memory.memory_end_num is None

    expire_glossary_memory(test_db, next_context, relation.memory_id, [MemoryType.RELATION])
    test_db.refresh(relation)
    assert relation.memory_end_num == next_chapter.chapter_num


def test_memory_and_glossary_deletion_preserve_independent_records(test_db: Session) -> None:
    admin = User(
        user_name="memory-admin",
        user_hashed_password="not-used",
        user_type=UserType.ADMIN,
    )
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Memory deletion source")
    test_db.add_all([admin, language, source_work])
    test_db.flush()

    novel = Novel(
        novel_title="Memory deletion novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    test_db.add(novel)
    test_db.flush()

    chapter_1 = Chapter(chapter_num=1, chapter_title="Chapter 1", chapter_is_public=False, novel_id=novel.novel_id)
    chapter_2 = Chapter(chapter_num=2, chapter_title="Chapter 2", chapter_is_public=False, novel_id=novel.novel_id)
    test_db.add_all([chapter_1, chapter_2])
    test_db.flush()
    content_1 = ChapterContent(
        chapter_content_text="Alpha and Beta",
        chapter_content_version=1,
        chapter_id=chapter_1.chapter_id,
    )
    content_2 = ChapterContent(
        chapter_content_text="Alpha and Beta return",
        chapter_content_version=1,
        chapter_id=chapter_2.chapter_id,
    )
    memory_group = MemoryGroup(
        memory_group_name="Memory deletion group",
        novel_id=novel.novel_id,
        memory_language=language.language_code,
    )
    test_db.add_all([content_1, content_2, memory_group])
    test_db.flush()

    alpha = create_term(test_db, memory_group.memory_group_id, "Alpha")
    beta = create_term(test_db, memory_group.memory_group_id, "Beta")
    context_1 = MemAccessContext(
        memory_group_id=memory_group.memory_group_id,
        chapter_id=chapter_1.chapter_id,
        chapter_content_id=content_1.chapter_content_id,
    )
    original, _ = create_memory(
        test_db,
        context_1,
        Creator.AGENT,
        MemoryType.FACT,
        ["Alpha"],
        "Alpha has an old property.",
    )
    independent, _ = create_memory(
        test_db,
        context_1,
        Creator.AGENT,
        MemoryType.FACT,
        ["Beta"],
        "Beta has an independent property.",
    )
    context_2 = MemAccessContext(
        memory_group_id=memory_group.memory_group_id,
        chapter_id=chapter_2.chapter_id,
        chapter_content_id=content_2.chapter_content_id,
    )
    successor, _ = supersede_memory(
        test_db,
        context_2,
        original.memory_id,
        Creator.AGENT,
        MemoryType.FACT,
        "Alpha has a new property.",
    )
    test_db.commit()

    delete_glossary_term(test_db, admin, memory_group.memory_group_id, beta.term_id)

    assert test_db.get(GlossaryTerm, beta.term_id) is None
    assert test_db.get(Memory, independent.memory_id) is not None
    assert test_db.get(GlossaryAssociation, (beta.term_id, independent.memory_id)) is None

    update_memory(test_db, admin, independent.memory_id, "Beta has an edited property.", "trait")
    test_db.refresh(independent)
    assert independent.memory_content == "Beta has an edited property."
    assert independent.mark == "trait"

    update_memory(test_db, admin, independent.memory_id, independent.memory_content, None)
    test_db.refresh(independent)
    assert independent.mark is None

    expire_memory(test_db, admin, independent.memory_id, chapter_2.chapter_id)
    test_db.refresh(independent)
    assert independent.memory_end_num == chapter_2.chapter_num

    delete_memory(test_db, admin, original.memory_id)
    test_db.refresh(successor)

    assert test_db.get(Memory, original.memory_id) is None
    assert successor.supersedes_memory_id is None
    assert test_db.get(GlossaryTerm, alpha.term_id) is not None
    assert (
        test_db.scalar(select(GlossaryAssociation).where(GlossaryAssociation.memory_id == successor.memory_id))
        is not None
    )
