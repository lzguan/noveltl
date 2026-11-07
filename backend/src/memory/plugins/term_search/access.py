from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Integer, Text, cast, column, func, select, values
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext, check_mem_access_ctx
from src.novels.models import Chapter, ChapterContent


@dataclass(frozen=True)
class TextOccurrences:
    text: str
    first_chapter_num: int | None
    chapter_count: int
    match_count: int


def count_text_occurrences(db: Session, ctx: MemAccessContext, texts: Sequence[str]) -> list[TextOccurrences]:
    distinct_texts = list(dict.fromkeys(texts))
    if not distinct_texts:
        return []
    end_chapter_num, novel_id = check_mem_access_ctx(db, ctx)
    contents = (
        select(Chapter.chapter_num, ChapterContent.chapter_content_text)
        .join(ChapterContent, ChapterContent.chapter_id == Chapter.chapter_id)
        .where(Chapter.novel_id == novel_id, Chapter.chapter_num <= end_chapter_num)
        .ext(distinct_on(Chapter.chapter_id))
        .order_by(Chapter.chapter_id, ChapterContent.chapter_content_version.desc())
        .subquery()
    )
    searched = values(column("text", Text), name="searched_texts").data([(text,) for text in distinct_texts])
    content = contents.c.chapter_content_text
    match_count = cast(
        (func.length(content) - func.length(func.replace(content, searched.c.text, ""))) / func.length(searched.c.text),
        Integer,
    )
    rows = db.execute(
        select(searched.c.text, func.min(contents.c.chapter_num), func.count(), func.sum(match_count))
        .select_from(searched)
        .join(contents, func.strpos(content, searched.c.text) > 0)
        .group_by(searched.c.text)
    ).all()
    found = {text: (first, chapters, matches) for text, first, chapters, matches in rows}
    return [
        TextOccurrences(text, *found[text]) if text in found else TextOccurrences(text, None, 0, 0)
        for text in distinct_texts
    ]
