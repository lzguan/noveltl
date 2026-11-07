from sqlalchemy import select
from sqlalchemy.orm import Session

from src.languages.models import Language
from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.conventions import context as context_module
from src.memory.agent.toolsets.conventions.context import conventions_context
from src.memory.models import MemoryGroup
from src.memory.plugins.conventions.access import create_convention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.translations.models import TermTranslation
from src.memory.types import Creator, MemoryType, ReviewStatus
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork

# Chapter 2's latest version drops 旧名; chapter 4 is after the anchor (chapter 3).
CHAPTER_TEXTS = {
    1: ["白玫走进来。"],
    2: ["旧名出现了。", "种级很重要。"],
    3: ["白玫谈到种级与方亭市。弃名也在。"],
    4: ["樱出现了。"],
}


def _setup(db: Session) -> tuple[MemoryGroup, dict[int, MemAccessContext]]:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Context source")
    db.add_all([language, source_work])
    db.flush()
    novel = Novel(
        novel_title="Context novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    db.add(novel)
    db.flush()
    group = MemoryGroup(memory_group_name="Context", novel_id=novel.novel_id, memory_language="zh")
    db.add(group)
    db.flush()
    contexts: dict[int, MemAccessContext] = {}
    for chapter_num, versions in CHAPTER_TEXTS.items():
        chapter = Chapter(
            chapter_num=chapter_num, chapter_title=f"Ch{chapter_num}", chapter_is_public=False, novel_id=novel.novel_id
        )
        db.add(chapter)
        db.flush()
        for version, text in enumerate(versions, start=1):
            content = ChapterContent(
                chapter_id=chapter.chapter_id, chapter_content_version=version, chapter_content_text=text
            )
            db.add(content)
            db.flush()
            contexts[chapter_num] = MemAccessContext(
                group.memory_group_id, chapter.chapter_id, content.chapter_content_id
            )
    for term, kind in [
        ("白玫", TermKind.PERSON),
        ("种级", TermKind.TITLE),
        ("方亭市", TermKind.PLACE),
        ("旧名", TermKind.PERSON),
        ("樱", TermKind.PERSON),
        ("弃名", TermKind.PERSON),
    ]:
        created = access.create_term(db, group.memory_group_id, term, kind)
        if term == "弃名":
            created.review_status = ReviewStatus.REJECTED
    db.commit()
    return group, contexts


def test_context_lists_range_terms_with_current_definitions_translations_and_conventions(test_db: Session) -> None:
    group, contexts = _setup(test_db)
    access.create_memory(test_db, contexts[1], Creator.AGENT, MemoryType.DEFINITION, ["白玫"], "Old definition.")
    access.create_memory(test_db, contexts[3], Creator.AGENT, MemoryType.DEFINITION, ["白玫"], "Current definition.")
    rejected, _ = access.create_memory(
        test_db, contexts[3], Creator.AGENT, MemoryType.DEFINITION, ["方亭市"], "Rejected definition."
    )
    rejected.memory_review_status = ReviewStatus.REJECTED
    access.create_memory(test_db, contexts[3], Creator.AGENT, MemoryType.DEFINITION, ["种级"], "长" * 300)
    terms = {term.term: term for term in test_db.scalars(select(GlossaryTerm))}
    test_db.add(TermTranslation(term_id=terms["白玫"].term_id, translation="White Rose", creator_type=Creator.USER))
    agent_draft = create_convention(
        test_db,
        group.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Ranks",
        rule="Use -rank.",
        rationale=None,
        creator_type=Creator.AGENT,
    )
    rejected_rule = create_convention(
        test_db,
        group.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Pinyin",
        rule="Use pinyin.",
        rationale="Readers asked.",
        creator_type=Creator.USER,
    )
    rejected_rule.review_status = ReviewStatus.REJECTED
    create_convention(
        test_db,
        group.memory_group_id,
        category=ConventionCategory.STYLE,
        title="Tone",
        rule="Keep it light.",
        rationale=None,
        creator_type=Creator.USER,
    )
    test_db.commit()
    deps = MemAgentDeps(db=test_db, mem_access_context=contexts[3])

    context = conventions_context(deps, 2)

    assert not context.terms_truncated
    # Grouped by kind; 旧名 is only in an old version, 樱 is after the anchor, 弃名 is rejected.
    assert [(term.term, term.kind, term.first_chapter_num) for term in context.terms] == [
        ("白玫", TermKind.PERSON, 3),
        ("方亭市", TermKind.PLACE, 3),
        ("种级", TermKind.TITLE, 2),
    ]
    by_term = {term.term: term for term in context.terms}
    assert (by_term["白玫"].definition, by_term["白玫"].translation) == ("Current definition.", "White Rose")
    assert by_term["方亭市"].definition is None
    definition = by_term["种级"].definition
    assert definition is not None and len(definition) == 200 and definition.endswith("…")
    # Every category, rejected ones included, with handles registered for the run.
    shown = {convention.title: convention for convention in context.conventions}
    assert set(shown) == {"Ranks", "Pinyin", "Tone"}
    assert shown["Tone"].category == ConventionCategory.STYLE
    assert shown["Ranks"].editable and not shown["Pinyin"].editable
    assert shown["Pinyin"].review_status == ReviewStatus.REJECTED
    assert deps.convention_handles.get_uuid(shown["Ranks"].handle) == agent_draft.convention_id


def test_range_terms_are_ordered_by_first_occurrence_and_capped(test_db: Session, monkeypatch) -> None:
    _, contexts = _setup(test_db)

    rows, truncated = access.get_terms_in_chapter_range(test_db, contexts[3], 2, limit=2)

    # First occurrences in chapters 2-3: 种级 (2), then 方亭市 and 白玫 (3).
    assert [(row.term.term, row.first_chapter_num) for row in rows] == [("种级", 2), ("方亭市", 3)]
    assert truncated

    monkeypatch.setattr(context_module, "MAX_CONTEXT_TERMS", 2)
    context = conventions_context(MemAgentDeps(db=test_db, mem_access_context=contexts[3]), 2)
    assert [term.term for term in context.terms] == ["方亭市", "种级"] and context.terms_truncated
