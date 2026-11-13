from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select

from src.files.access import fetch_file
from src.files.storage import ObjectStore
from src.memory.models import MemoryGroup
from src.memory.types import MemoryType, PluginName
from src.novels.models import Chapter, ChapterContent
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.common.memory_inputs import iter_batch_memories
from src.translations.jsonl import iter_translation_records
from src.translations.models import TranslationJob, TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, TranslationRecord
from src.translations.types import ACTIONS, ActionName, ActionType, TranslationTaskStatus
from src.translations.validation import validate_output_records

_action_name = TypeAdapter(ActionName)


@dataclass(frozen=True)
class MemoryInputs:
    memory_group_id: UUID
    plugin_names: list[PluginName] | None = None
    memory_types: list[MemoryType] | None = None
    exclude_current_chapter: bool = True


def iter_initial_records(
    context: ActionTaskContext, stage: TranslationStage, memories: MemoryInputs | None
) -> Iterator[TranslationRecord]:
    db, batch_id = context.db, context.task.batch_id
    if memories is not None:
        group = db.scalar(
            select(MemoryGroup.memory_group_id)
            .join(TranslationJob, TranslationJob.novel_id == MemoryGroup.novel_id)
            .where(TranslationJob.job_id == stage.job_id, MemoryGroup.memory_group_id == memories.memory_group_id)
        )
        if group is None:
            raise ValueError("Memory group does not belong to the translation job's novel")
    rows = db.execute(
        select(TranslationJobChapter.chapter_id, ChapterContent.chapter_content_text)
        .join(ChapterContent, ChapterContent.chapter_content_id == TranslationJobChapter.source_chapter_content_id)
        .join(Chapter, Chapter.chapter_id == TranslationJobChapter.chapter_id)
        .where(TranslationJobChapter.job_id == stage.job_id, TranslationJobChapter.batch_id == batch_id)
        .order_by(Chapter.chapter_num, Chapter.chapter_id)
        .execution_options(yield_per=100)
    )
    for chapter_id, content in rows:
        yield ChapterRecord(chapter_id=chapter_id, stream="chapter", payload=content)
    if memories is not None:
        yield from iter_batch_memories(
            db,
            job_id=stage.job_id,
            batch_id=batch_id,
            memory_group_id=memories.memory_group_id,
            plugin_names=memories.plugin_names,
            memory_types=memories.memory_types,
            exclude_current_chapter=memories.exclude_current_chapter,
        )


def _sources(context: ActionTaskContext, stage: TranslationStage, needs: ActionType) -> dict[UUID, set[str]]:
    earlier = context.db.execute(
        select(TranslationTask.status, TranslationTask.failed_at, TranslationTask.output_file_id, TranslationStage)
        .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
        .where(
            TranslationTask.batch_id == context.task.batch_id,
            TranslationStage.job_id == stage.job_id,
            TranslationStage.stage_num < stage.stage_num,
        )
        .order_by(TranslationStage.stage_num.desc())
    ).all()
    remaining = set(needs)
    sources: dict[UUID, set[str]] = {}
    for status, failed_at, output_file_id, producer in earlier:
        produced = remaining & ACTIONS[_action_name.validate_python(producer.action)].outputs.keys()
        if not produced:
            continue
        if status != TranslationTaskStatus.COMPLETE or failed_at is not None or output_file_id is None:
            raise ValueError(f"Stage {producer.stage_num} must have a completed output artifact")
        sources.setdefault(output_file_id, set()).update(produced)
        remaining -= produced
    if remaining:
        raise ValueError(f"No earlier stage produces: {', '.join(sorted(remaining))}")
    return sources


def resolve_inputs(
    context: ActionTaskContext, store: ObjectStore, stage: TranslationStage, needs: ActionType
) -> Iterator[TranslationRecord]:
    chapter_ids = list(
        context.db.scalars(
            select(TranslationJobChapter.chapter_id).where(
                TranslationJobChapter.job_id == stage.job_id,
                TranslationJobChapter.batch_id == context.task.batch_id,
            )
        )
    )
    if not chapter_ids:
        raise ValueError("Cannot resolve inputs for an empty translation batch")
    for file_id, names in _sources(context, stage, needs).items():
        records = (
            record
            for record in iter_translation_records(fetch_file(context.db, store, file_id))
            if record.key.stream in names
        )
        output_type = {name: needs[name] for name in names}
        yield from validate_output_records(records, chapter_ids=chapter_ids, output_type=output_type)
