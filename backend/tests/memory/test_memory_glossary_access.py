from sqlalchemy.orm import Session

from src.languages.models import Language
from src.memory.access import MemAccessContext
from src.memory.glossary.access import create_memory, create_term, inspect_terms
from src.memory.models import MemoryGroup
from src.memory.types import Creator, MemoryType
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork


def test_inspect_terms_filters_memory_types(test_db: Session) -> None:
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
    memory_group = MemoryGroup(
        memory_group_name="Memory test group",
        novel_id=novel.novel_id,
        memory_language=language.language_code,
    )
    test_db.add_all([chapter_content, memory_group])
    test_db.flush()

    create_term(test_db, memory_group.memory_group_id, "Alpha")
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
    test_db.commit()

    assert [memory.memory_id for memory, _ in inspect_terms(test_db, context, ["Alpha"], [MemoryType.FACT])] == [
        fact.memory_id
    ]
    assert [
        memory.memory_id for memory, _ in inspect_terms(test_db, context, ["Alpha"], [MemoryType.RELATION])
    ] == [relation.memory_id]
    assert {memory.memory_id for memory, _ in inspect_terms(test_db, context, ["Alpha"], None)} == {
        fact.memory_id,
        relation.memory_id,
    }
    assert inspect_terms(test_db, context, ["Alpha"], []) == []
