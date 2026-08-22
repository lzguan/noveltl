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
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.glossary.service import delete_glossary_term
from src.memory.service import delete_memory, expire_memory
from src.memory.types import Creator, MemoryType
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

    alpha = create_term(test_db, memory_group.memory_group_id, "Alpha")
    create_term(test_db, memory_group.memory_group_id, "Beta")
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
    )
    relation, _ = create_memory(
        test_db,
        context,
        Creator.AGENT,
        MemoryType.RELATION,
        ["Alpha", "Beta"],
        "Alpha is related to Beta.",
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
    assert relation.plugin_name == GLOSSARY_PLUGIN_NAME

    assert [memory.memory_id for memory, _ in inspect_terms(test_db, context, ["Alpha"], [MemoryType.FACT])] == [
        fact.memory_id
    ]
    assert [memory.memory_id for memory, _ in inspect_terms(test_db, context, ["Alpha"], [MemoryType.RELATION])] == [
        relation.memory_id
    ]
    assert {memory.memory_id for memory, _ in inspect_terms(test_db, context, ["Alpha"], None)} == {
        fact.memory_id,
        relation.memory_id,
    }
    assert inspect_terms(test_db, context, ["Alpha"], []) == []

    next_context = MemAccessContext(
        memory_group_id=memory_group.memory_group_id,
        chapter_id=next_chapter.chapter_id,
        chapter_content_id=next_chapter_content.chapter_content_id,
    )
    with pytest.raises(MemoryNotFoundException):
        supersede_memory(
            test_db,
            next_context,
            other_plugin_memory.memory_id,
            Creator.AGENT,
            MemoryType.FACT,
            "Glossary must not supersede this memory.",
        )

    test_db.refresh(other_plugin_memory)
    assert other_plugin_memory.memory_end_num is None


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
