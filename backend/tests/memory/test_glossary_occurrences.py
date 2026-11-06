from sqlalchemy import select
from sqlalchemy.orm import Session

from src.languages.models import Language
from src.memory.access import MemAccessContext
from src.memory.models import MemoryGroup
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.glossary.occurrences import (
    TermOccurrences,
    get_term_occurrences,
    get_terms_in_chapter_range,
)
from src.memory.plugins.glossary.types import TermKind
from src.memory.types import ReviewStatus
from src.novels.constants import NovelType, Visibility
from src.novels.models import Chapter, ChapterContent, Novel, SourceWork

# Chapter 2's latest version drops 旧名; chapter 4 is after the anchor (chapter 3).
CHAPTER_TEXTS = {
    1: ["白玫走进来。"],
    2: ["旧名出现了。", "这一章没有术语。"],
    3: ["白玫和白玫谈到『种』级，种级很重要。弃名也在。百分之10%_。"],
    4: ["樱出现了，白玫也在。"],
}


def _make_group(test_db: Session) -> tuple[MemoryGroup, MemAccessContext]:
    language = Language(language_name="Chinese", language_code="zh")
    source_work = SourceWork(source_work_title="Occurrence source")
    test_db.add_all([language, source_work])
    test_db.flush()
    novel = Novel(
        novel_title="Occurrence novel",
        novel_description=None,
        novel_author=None,
        novel_visibility=Visibility.PRIVATE,
        novel_type=NovelType.ORIGINAL,
        source_work_id=source_work.source_work_id,
        language_code=language.language_code,
    )
    test_db.add(novel)
    test_db.flush()
    contents: dict[int, ChapterContent] = {}
    for chapter_num, versions in CHAPTER_TEXTS.items():
        chapter = Chapter(
            chapter_num=chapter_num,
            chapter_title=f"Chapter {chapter_num}",
            chapter_is_public=False,
            novel_id=novel.novel_id,
        )
        test_db.add(chapter)
        test_db.flush()
        for version, text in enumerate(versions, start=1):
            content = ChapterContent(
                chapter_id=chapter.chapter_id, chapter_content_version=version, chapter_content_text=text
            )
            test_db.add(content)
            contents[chapter_num] = content
    group = MemoryGroup(memory_group_name="Occurrences", novel_id=novel.novel_id, memory_language="zh")
    test_db.add(group)
    test_db.flush()
    for term, kind in [
        ("白玫", TermKind.PERSON),
        ("种级", TermKind.TITLE),
        ("旧名", TermKind.PERSON),
        ("樱", TermKind.PERSON),
        ("弃名", TermKind.PERSON),
    ]:
        access.create_term(test_db, group.memory_group_id, term, kind)
    rejected = test_db.scalars(select(GlossaryTerm).where(GlossaryTerm.term == "弃名")).one()
    rejected.review_status = ReviewStatus.REJECTED
    test_db.commit()
    anchor = contents[3]
    return group, MemAccessContext(group.memory_group_id, anchor.chapter_id, anchor.chapter_content_id)


def test_range_terms_use_latest_content_up_to_the_anchor_and_skip_rejected_terms(test_db: Session) -> None:
    _, ctx = _make_group(test_db)

    count, terms = get_terms_in_chapter_range(test_db, ctx, None, limit=10)

    # 旧名 is only in chapter 2's old version, 樱 only after the anchor, 弃名 is rejected.
    assert count == 2
    assert [(row.term.term, row.first_chapter_num) for row in terms] == [("白玫", 1), ("种级", 3)]

    count, terms = get_terms_in_chapter_range(test_db, ctx, 2, limit=10)
    assert [(row.term.term, row.first_chapter_num) for row in terms] == [("白玫", 3), ("种级", 3)]

    count, terms = get_terms_in_chapter_range(test_db, ctx, None, limit=1)
    assert count == 2 and len(terms) == 1


def test_term_occurrences_count_raw_matches_and_report_first_appearance(test_db: Session) -> None:
    _, ctx = _make_group(test_db)

    occurrences = get_term_occurrences(test_db, ctx, ["种级", "白玫", "樱", "未知", "白玫"], 3)

    assert occurrences == [
        # Matching is on raw text: 『种』级 is not an occurrence of 种级.
        TermOccurrences(term="种级", first_chapter_num=3, total_occurrences=1, chapter_occurrences=[(3, 1)]),
        # Chapter 1 counts towards the total and first appearance, but is before the range.
        TermOccurrences(term="白玫", first_chapter_num=1, total_occurrences=3, chapter_occurrences=[(3, 2)]),
        # A glossary term that never appears up to the anchor; unknown names are omitted.
        TermOccurrences(term="樱", first_chapter_num=None, total_occurrences=0, chapter_occurrences=[]),
    ]


def test_term_search_ignores_source_marks_and_escapes_wildcards(test_db: Session) -> None:
    group, _ = _make_group(test_db)
    access.create_term(test_db, group.memory_group_id, "100%纯度")

    assert [term.term for term in access.search_terms(test_db, group.memory_group_id, "『级』", limit=10)[1]] == [
        "种级"
    ]
    assert [term.term for term in access.search_terms(test_db, group.memory_group_id, "%", limit=10)[1]] == ["100%纯度"]
    count, terms = access.search_terms(test_db, group.memory_group_id, "名", limit=10)
    assert count == 1 and [term.term for term in terms] == ["旧名"]
    count, terms = access.search_terms(test_db, group.memory_group_id, "名", limit=10, include_rejected=True)
    assert count == 2


def test_range_terms_treat_like_wildcards_in_terms_literally(test_db: Session) -> None:
    group, ctx = _make_group(test_db)
    # As a LIKE pattern, 1%_ would match chapter 3's "10%_"; as text it does not occur.
    access.create_term(test_db, group.memory_group_id, "1%_")
    access.create_term(test_db, group.memory_group_id, "10%_")

    _, terms = get_terms_in_chapter_range(test_db, ctx, None, limit=10)

    assert "1%_" not in {row.term.term for row in terms}
    assert "10%_" in {row.term.term for row in terms}
