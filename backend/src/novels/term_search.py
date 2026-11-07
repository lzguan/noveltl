"""Exact substring search over chapter text, limited to chapters the user can read.

Text is matched raw on each chapter's latest content (or a pinned version).
Occurrences are non-overlapping, and offsets are Python string indices (code
points); they equal JavaScript UTF-16 offsets only for text inside the Basic
Multilingual Plane, as label offsets already assume.
"""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Integer, Select, Text, cast, column, func, select, values
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from src.auth.models import User
from src.novels.exceptions import ChapterContentNotFoundException
from src.novels.models import Chapter, ChapterContent
from src.novels.permissions import chapter_content_mod_access_select, chapter_mod_access_select
from src.novels.schemas import (
    ChapterContentTermSearch,
    ChapterTermMatches,
    NovelTermSearch,
    TermOccurrencePreview,
)
from src.novels.service import query_novel_by_id

MAX_CHAPTERS_PER_PAGE = 100
PREVIEW_CONTEXT = 40


def find_occurrences(text: str, term: str) -> list[int]:
    """Start offsets of non-overlapping occurrences of ``term``, left to right."""
    return [match.start() for match in re.finditer(re.escape(term), text)]


def _latest_readable_contents(
    current_user: User | None, novel_id: uuid.UUID, start_chapter_num: int | None, end_chapter_num: int | None
) -> Select[uuid.UUID, int, uuid.UUID, str]:
    """Each readable chapter's latest content, optionally within [start, end] chapter numbers."""
    statement = (
        select(
            Chapter.chapter_id,
            Chapter.chapter_num,
            ChapterContent.chapter_content_id,
            ChapterContent.chapter_content_text,
        )
        .join(ChapterContent, ChapterContent.chapter_id == Chapter.chapter_id)
        .where(Chapter.novel_id == novel_id)
        .ext(distinct_on(Chapter.chapter_id))
        .order_by(Chapter.chapter_id, ChapterContent.chapter_content_version.desc())
    )
    if start_chapter_num is not None:
        statement = statement.where(Chapter.chapter_num >= start_chapter_num)
    if end_chapter_num is not None:
        statement = statement.where(Chapter.chapter_num <= end_chapter_num)
    return chapter_mod_access_select(statement, current_user)


def search_novel(
    db: Session,
    current_user: User | None,
    novel_id: uuid.UUID,
    term: str,
    *,
    start_chapter_num: int | None = None,
    end_chapter_num: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> NovelTermSearch:
    """
    Find every occurrence of a term in the latest content of a novel's readable chapters.

    Args:
        db: Database which we are querying.
        current_user: User that is searching; only chapters they can read are searched.
        novel_id: ID of the novel to search.
        term: Exact text to find.
        start_chapter_num: First chapter number to search (inclusive), or None for the first chapter.
        end_chapter_num: Last chapter number to search (inclusive), or None for the last chapter.
        offset: Number of matching chapters to skip.
        limit: Maximum number of matching chapters to return, capped at MAX_CHAPTERS_PER_PAGE.

    Returns:
        One page of matching chapters in chapter order with their match counts, and totals for the whole range.

    Raises:
        NovelNotFoundException: The novel does not exist or is not readable.
    """
    limit = min(limit, MAX_CHAPTERS_PER_PAGE)
    contents = _latest_readable_contents(current_user, novel_id, start_chapter_num, end_chapter_num).subquery()
    text = contents.c.chapter_content_text
    # replace() removes non-overlapping matches left to right, like find_occurrences.
    match_count = cast((func.length(text) - func.length(func.replace(text, term, ""))) / func.length(term), Integer)
    matches = (
        select(
            contents.c.chapter_id,
            contents.c.chapter_num,
            contents.c.chapter_content_id,
            match_count.label("match_count"),
        )
        .where(func.strpos(text, term) > 0)
        .subquery()
    )

    # Window totals are computed before OFFSET/LIMIT, so one scan gives the page and the totals.
    rows = db.execute(
        select(
            matches.c.chapter_id,
            matches.c.chapter_num,
            matches.c.chapter_content_id,
            matches.c.match_count,
            func.count().over().label("total_chapters"),
            func.sum(matches.c.match_count).over().label("total_matches"),
        )
        .order_by(matches.c.chapter_num, matches.c.chapter_id)
        .offset(offset)
        .limit(limit + 1)
    ).all()

    if rows:
        total_chapters, total_matches = rows[0].total_chapters, rows[0].total_matches
    elif offset > 0:
        # Past the last page: the window has no rows to report totals on.
        total_chapters, total_matches = db.execute(
            select(func.count(), func.coalesce(func.sum(matches.c.match_count), 0))
        ).one()
    else:
        total_chapters, total_matches = 0, 0
    if total_chapters == 0:
        query_novel_by_id(db, current_user, novel_id)

    return NovelTermSearch(
        total_chapters=total_chapters,
        total_matches=total_matches,
        next_offset=offset + limit if len(rows) > limit else None,
        chapters=[
            ChapterTermMatches(
                chapter_id=row.chapter_id,
                chapter_num=row.chapter_num,
                chapter_content_id=row.chapter_content_id,
                match_count=row.match_count,
            )
            for row in rows[:limit]
        ],
    )


def search_chapter_content(
    db: Session, current_user: User | None, chapter_content_id: uuid.UUID, term: str
) -> ChapterContentTermSearch:
    """
    Find every occurrence of a term in one chapter content version, with surrounding text from its line.

    Args:
        db: Database which we are querying.
        current_user: User that is searching.
        chapter_content_id: ID of the content version to search.
        term: Exact text to find.

    Returns:
        Every occurrence in order, each with a preview clipped to its line.

    Raises:
        ChapterContentNotFoundException: The content does not exist or is not readable.
    """
    statement = chapter_content_mod_access_select(
        select(ChapterContent.chapter_content_text).where(ChapterContent.chapter_content_id == chapter_content_id),
        current_user,
    )
    text = db.scalar(statement)
    if text is None:
        raise ChapterContentNotFoundException
    previews: list[TermOccurrencePreview] = []
    for start in find_occurrences(text, term):
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", start + len(term))
        line_end = len(text) if line_end == -1 else line_end
        preview_start = max(line_start, start - PREVIEW_CONTEXT)
        preview_end = min(line_end, start + len(term) + PREVIEW_CONTEXT)
        previews.append(
            TermOccurrencePreview(start=start, preview=text[preview_start:preview_end], preview_start=preview_start)
        )
    return ChapterContentTermSearch(chapter_content_id=chapter_content_id, occurrences=previews)


@dataclass(frozen=True)
class TermOccurrenceSummary:
    """How often one term occurs in a novel up to a chapter.

    Attributes:
        term: The searched text.
        first_chapter_num: The first chapter containing it, or None if no chapter does.
        chapter_count: Number of chapters containing it.
        match_count: Number of non-overlapping occurrences across those chapters.
    """

    term: str
    first_chapter_num: int | None
    chapter_count: int
    match_count: int


def summarize_occurrences(
    db: Session, novel_id: uuid.UUID, terms: Sequence[str], end_chapter_num: int
) -> list[TermOccurrenceSummary]:
    """Summarize occurrences of each term in the latest content of chapters up to a chapter.

    Applies no permission filter.

    Args:
        db: The database session.
        novel_id: The novel to search.
        terms: Exact texts to find; duplicates are summarized once.
        end_chapter_num: Last chapter searched (inclusive).

    Returns:
        One summary per distinct term, in the order given.
    """
    distinct_terms = list(dict.fromkeys(terms))
    if not distinct_terms:
        return []
    contents = (
        select(Chapter.chapter_num, ChapterContent.chapter_content_text)
        .join(ChapterContent, ChapterContent.chapter_id == Chapter.chapter_id)
        .where(Chapter.novel_id == novel_id, Chapter.chapter_num <= end_chapter_num)
        .ext(distinct_on(Chapter.chapter_id))
        .order_by(Chapter.chapter_id, ChapterContent.chapter_content_version.desc())
        .subquery()
    )
    searched = values(column("term", Text), name="searched_terms").data([(term,) for term in distinct_terms])
    text = contents.c.chapter_content_text
    match_count = cast(
        (func.length(text) - func.length(func.replace(text, searched.c.term, ""))) / func.length(searched.c.term),
        Integer,
    )
    rows = db.execute(
        select(searched.c.term, func.min(contents.c.chapter_num), func.count(), func.sum(match_count))
        .select_from(searched)
        .join(contents, func.strpos(text, searched.c.term) > 0)
        .group_by(searched.c.term)
    ).all()
    found = {term: (first, chapters, matches) for term, first, chapters, matches in rows}
    return [
        TermOccurrenceSummary(term, *found[term]) if term in found else TermOccurrenceSummary(term, None, 0, 0)
        for term in distinct_terms
    ]
