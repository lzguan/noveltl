"""Batch memory retrieval for translation preparation."""

from collections.abc import Generator
from itertools import groupby
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.memory.models import Memory as MemoryRow
from src.memory.models import MemoryGroup
from src.memory.schemas import Memory
from src.memory.types import MemoryType, PluginName, ReviewStatus
from src.novels.models import Chapter
from src.translations.models import TranslationJob, TranslationJobChapter
from src.translations.records import MemoriesRecord


def iter_batch_memories(
    db: Session,
    *,
    job_id: UUID,
    batch_id: UUID,
    memory_group_id: UUID,
    plugin_names: list[PluginName] | None = None,
    memory_types: list[MemoryType] | None = None,
    exclude_current_chapter: bool = True,
) -> Generator[MemoriesRecord, None, None]:
    """Read one ordered candidate list per chapter using a single SQL query.

    Include pending/approved memories active at N (end > N), optionally excluding
    starts at N. This does not reconstruct the memory state immediately before N.
    Only groups belonging to the job's novel can match. Empty selections produce
    empty records; None disables an optional filter, while [] matches nothing.
    The caller owns the session/transaction and must exhaust or close the iterator.
    """
    conditions = [
        MemoryRow.memory_group_id == memory_group_id,
        select(MemoryGroup.memory_group_id)
        .where(
            MemoryGroup.memory_group_id == MemoryRow.memory_group_id,
            MemoryGroup.novel_id == TranslationJob.novel_id,
        )
        .exists(),
        MemoryRow.memory_start_num < Chapter.chapter_num
        if exclude_current_chapter
        else MemoryRow.memory_start_num <= Chapter.chapter_num,
        or_(MemoryRow.memory_end_num.is_(None), MemoryRow.memory_end_num > Chapter.chapter_num),
        MemoryRow.memory_review_status != ReviewStatus.REJECTED,
    ]
    if plugin_names is not None:
        conditions.append(MemoryRow.plugin_name.in_(plugin_names))
    if memory_types is not None:
        conditions.append(MemoryRow.memory_type.in_(memory_types))
    statement = (
        select(TranslationJobChapter.chapter_id, MemoryRow)
        .select_from(TranslationJobChapter)
        .join(TranslationJob, TranslationJob.job_id == TranslationJobChapter.job_id)
        .join(
            Chapter,
            and_(
                Chapter.chapter_id == TranslationJobChapter.chapter_id,
                Chapter.novel_id == TranslationJob.novel_id,
            ),
        )
        .outerjoin(MemoryRow, and_(*conditions))
        .where(TranslationJobChapter.job_id == job_id, TranslationJobChapter.batch_id == batch_id)
        .order_by(
            Chapter.chapter_num,
            TranslationJobChapter.chapter_id,
            MemoryRow.memory_start_num.desc(),
            MemoryRow.memory_id,
        )
        .execution_options(yield_per=100)
    )
    result = db.execute(statement)
    try:
        for chapter_id, rows in groupby(result, key=lambda row: row._t[0]):
            yield MemoriesRecord(
                chapter_id=chapter_id,
                payload=[Memory.model_validate(memory) for _, memory in rows if memory is not None],
            )
    finally:
        result.close()
