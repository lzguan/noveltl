from collections.abc import Iterator, Mapping
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.files.access import fetch_file
from src.files.storage import ObjectStore
from src.memory.models import MemoryGroup
from src.novels.models import Chapter, ChapterContent
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.common.memory_inputs import iter_batch_memories
from src.translations.jsonl import iter_translation_records
from src.translations.models import TranslationJob, TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, TranslationRecord
from src.translations.schemas import MemoriesInput, TranslationInput, TranslationJobConfig
from src.translations.types import ACTIONS, ActionName, ActionSignature, ActionType, TranslationTaskStatus
from src.translations.validation import validate_output_records

_action_name = TypeAdapter(ActionName)


def job_config(db: Session, job_id: UUID) -> TranslationJobConfig:
    return TranslationJobConfig.model_validate(
        db.execute(select(TranslationJob.config).where(TranslationJob.job_id == job_id)).scalar_one()
    )


def stage_signature(config: TranslationJobConfig, stage: TranslationStage) -> ActionSignature:
    return ACTIONS[_action_name.validate_python(stage.action)](config.input_type())


def batch_chapter_ids(context: ActionTaskContext, stage: TranslationStage) -> list[UUID]:
    chapter_ids = list(
        context.db.scalars(
            select(TranslationJobChapter.chapter_id).where(
                TranslationJobChapter.job_id == stage.job_id,
                TranslationJobChapter.batch_id == context.task.batch_id,
            )
        )
    )
    if not chapter_ids:
        raise ValueError("Translation batch has no chapters")
    return chapter_ids


def iter_initial_records(
    context: ActionTaskContext, stage: TranslationStage, inputs: Mapping[str, TranslationInput]
) -> Iterator[TranslationRecord]:
    db, batch_id = context.db, context.task.batch_id
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
    for name, source in inputs.items():
        match source:
            case MemoriesInput():
                group = db.scalar(
                    select(MemoryGroup.memory_group_id)
                    .join(TranslationJob, TranslationJob.novel_id == MemoryGroup.novel_id)
                    .where(TranslationJob.job_id == stage.job_id, MemoryGroup.memory_group_id == source.memory_group_id)
                )
                if group is None:
                    raise ValueError("Memory group does not belong to the translation job's novel")
                yield from iter_batch_memories(
                    db,
                    job_id=stage.job_id,
                    batch_id=batch_id,
                    memory_group_id=source.memory_group_id,
                    plugin_names=source.plugin_names,
                    memory_types=source.memory_types,
                    exclude_current_chapter=source.exclude_current_chapter,
                    stream=name,
                )


def _sources(context: ActionTaskContext, stage: TranslationStage, needs: ActionType) -> dict[UUID, set[str]]:
    config = job_config(context.db, stage.job_id)
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
        signature = stage_signature(config, producer)
        dropped = remaining & signature.drops
        if dropped:
            raise ValueError(f"Stage {producer.stage_num} drops: {', '.join(sorted(dropped))}")
        produced = remaining & signature.outputs.keys()
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
    chapter_ids = batch_chapter_ids(context, stage)
    for file_id, names in _sources(context, stage, needs).items():
        records = (
            record
            for record in iter_translation_records(fetch_file(context.db, store, file_id))
            if record.key.stream in names
        )
        output_type = {name: needs[name] for name in names}
        yield from validate_output_records(records, chapter_ids=chapter_ids, output_type=output_type)
