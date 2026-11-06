"""Glossary reads over ranges of chapter text, bounded by the access context's chapter.

Matching uses each chapter's latest content and ``contains_query`` (raw text). Chapters after the context's chapter are never read.
Functions here apply no caller policy and never commit.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Subquery, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext, check_mem_access_ctx
from src.memory.plugins.glossary.access import contains_query
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.types import ReviewStatus
from src.novels.models import Chapter, ChapterContent


def _latest_chapter_texts(novel_id: UUID, start_chapter_num: int | None, end_chapter_num: int) -> Subquery:
    """Latest content of each chapter numbered within [start, end]; no start means the first chapter."""
    statement = (
        select(Chapter.chapter_num, ChapterContent.chapter_content_text.label("text"))
        .join(ChapterContent, ChapterContent.chapter_id == Chapter.chapter_id)
        .where(Chapter.novel_id == novel_id, Chapter.chapter_num <= end_chapter_num)
        .ext(distinct_on(Chapter.chapter_id))
        .order_by(Chapter.chapter_id, ChapterContent.chapter_content_version.desc())
    )
    if start_chapter_num is not None:
        statement = statement.where(Chapter.chapter_num >= start_chapter_num)
    return statement.subquery()


@dataclass(frozen=True)
class RangeTerm:
    term: GlossaryTerm
    first_chapter_num: int
    """First chapter within the range whose text contains the term."""


def get_terms_in_chapter_range(
    db: Session,
    ctx: MemAccessContext,
    start_chapter_num: int | None,
    *,
    limit: int,
    include_rejected: bool = False,
) -> tuple[int, list[RangeTerm]]:
    """Terms occurring in chapters [start, context chapter], by kind then first appearance.

    Returns the total number of matching terms and at most ``limit`` of them.
    """
    end_chapter_num, novel_id = check_mem_access_ctx(db, ctx)
    texts = _latest_chapter_texts(novel_id, start_chapter_num, end_chapter_num)
    first_chapter_num = func.min(texts.c.chapter_num).label("first_chapter_num")
    statement = (
        select(GlossaryTerm, first_chapter_num)
        .join(texts, contains_query(texts.c.text, GlossaryTerm.term))
        .where(GlossaryTerm.memory_group_id == ctx.memory_group_id)
        .group_by(GlossaryTerm.term_id)
    )
    if not include_rejected:
        statement = statement.where(GlossaryTerm.review_status != ReviewStatus.REJECTED)
    count = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.execute(
        statement.order_by(GlossaryTerm.term_kind, first_chapter_num, GlossaryTerm.term).limit(limit)
    ).all()
    return count, [RangeTerm(term=term, first_chapter_num=first) for term, first in rows]


@dataclass(frozen=True)
class TermOccurrences:
    term: str
    first_chapter_num: int | None
    """First chapter up to the context chapter that contains the term; None if none does."""
    total_occurrences: int
    """Non-overlapping occurrences across those chapters."""
    chapter_occurrences: list[tuple[int, int]]
    """(chapter number, occurrences) for chapters within [start, context chapter] that contain the term."""


def get_term_occurrences(
    db: Session,
    ctx: MemAccessContext,
    term_names: Sequence[str],
    start_chapter_num: int | None,
) -> list[TermOccurrences]:
    """Occurrence counts of the group's exact glossary terms, in the order requested.

    Names that are not glossary terms in this group are omitted.
    """
    end_chapter_num, novel_id = check_mem_access_ctx(db, ctx)
    texts = _latest_chapter_texts(novel_id, None, end_chapter_num)
    text = texts.c.text
    term = GlossaryTerm.term
    occurrences = (func.length(text) - func.length(func.replace(text, term, ""))) / func.nullif(func.length(term), 0)
    rows = db.execute(
        select(GlossaryTerm.term, texts.c.chapter_num, occurrences)
        .join(texts, contains_query(texts.c.text, GlossaryTerm.term))
        .where(GlossaryTerm.memory_group_id == ctx.memory_group_id, GlossaryTerm.term.in_(term_names))
        .order_by(texts.c.chapter_num)
    ).all()
    known = set(
        db.scalars(
            select(GlossaryTerm.term).where(
                GlossaryTerm.memory_group_id == ctx.memory_group_id, GlossaryTerm.term.in_(term_names)
            )
        )
    )
    by_term: dict[str, list[tuple[int, int]]] = {name: [] for name in known}
    for name, chapter_num, count in rows:
        by_term[name].append((chapter_num, int(count or 0)))
    result: list[TermOccurrences] = []
    for name in dict.fromkeys(term_names):
        if name not in by_term:
            continue
        chapters = by_term[name]
        result.append(
            TermOccurrences(
                term=name,
                first_chapter_num=chapters[0][0] if chapters else None,
                total_occurrences=sum(count for _, count in chapters),
                chapter_occurrences=[
                    (chapter_num, count)
                    for chapter_num, count in chapters
                    if start_chapter_num is None or chapter_num >= start_chapter_num
                ],
            )
        )
    return result
