from collections.abc import AsyncIterable, AsyncIterator, Collection, Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.files.access import fetch_file
from src.files.async_storage import AsyncObjectStore
from src.memory.models import MemoryGroup
from src.memory.plugins.conventions.access import read_conventions
from src.memory.types import ReviewStatus
from src.novels.models import Chapter, ChapterContent
from src.translations.actions.actions import ActionTaskContext
from src.translations.actions.common.memory_inputs import iter_batch_memories
from src.translations.actions.common.term_inputs import read_term_translation_map
from src.translations.jsonl import aiter_translation_records
from src.translations.models import TranslationJob, TranslationJobChapter, TranslationStage, TranslationTask
from src.translations.records import ChapterRecord, ConventionContent, ConventionsRecord, TermsRecord, TranslationRecord
from src.translations.schemas import ConventionsInput, MemoriesInput, TermsInput, TranslationInput, stage_config
from src.translations.types import (
    ActionSignature,
    ActionType,
    TranslationTaskStatus,
    infer_pipeline,
)
from src.translations.validation import validate_output_records


async def batch_chapter_ids(context: ActionTaskContext, stage: TranslationStage) -> list[UUID]:
    chapter_ids = list(
        await context.db.scalars(
            select(TranslationJobChapter.chapter_id).where(
                TranslationJobChapter.job_id == stage.job_id,
                TranslationJobChapter.batch_id == context.task.batch_id,
            )
        )
    )
    if not chapter_ids:
        raise ValueError("Translation batch has no chapters")
    return chapter_ids


async def iter_initial_records(
    context: ActionTaskContext, stage: TranslationStage, inputs: Mapping[str, TranslationInput]
) -> AsyncIterator[TranslationRecord]:
    db, batch_id = context.db, context.task.batch_id
    chapters = list(
        await db.execute(
            select(TranslationJobChapter.chapter_id, ChapterContent.chapter_content_text)
            .join(ChapterContent, ChapterContent.chapter_content_id == TranslationJobChapter.source_chapter_content_id)
            .join(Chapter, Chapter.chapter_id == TranslationJobChapter.chapter_id)
            .where(TranslationJobChapter.job_id == stage.job_id, TranslationJobChapter.batch_id == batch_id)
            .order_by(Chapter.chapter_num, Chapter.chapter_id)
        )
    )
    for chapter_id, content in chapters:
        yield ChapterRecord(chapter_id=chapter_id, stream="chapter", payload=content)
    for name, source in inputs.items():
        group = await db.scalar(
            select(MemoryGroup.memory_group_id)
            .join(TranslationJob, TranslationJob.novel_id == MemoryGroup.novel_id)
            .where(TranslationJob.job_id == stage.job_id, MemoryGroup.memory_group_id == source.memory_group_id)
        )
        if group is None:
            raise ValueError("Memory group does not belong to the translation job's novel")
        match source:
            case MemoriesInput():
                memories = iter_batch_memories(
                    db,
                    job_id=stage.job_id,
                    batch_id=batch_id,
                    memory_group_id=source.memory_group_id,
                    plugin_names=source.plugin_names,
                    memory_types=source.memory_types,
                    exclude_current_chapter=source.exclude_current_chapter,
                    stream=name,
                )
                async for record in memories:
                    yield record
            case TermsInput():
                translations = await read_term_translation_map(db, source.memory_group_id)
                for chapter_id, content in chapters:
                    yield TermsRecord(
                        chapter_id=chapter_id,
                        stream=name,
                        payload={term: translation for term, translation in translations.items() if term in content},
                    )
            case ConventionsInput():
                conventions = [
                    ConventionContent(
                        category=convention.category,
                        title=convention.title,
                        rule=convention.rule,
                        rationale=convention.rationale,
                    )
                    for convention in await read_conventions(
                        db, source.memory_group_id, review_statuses=[ReviewStatus.PENDING, ReviewStatus.APPROVED]
                    )
                ]
                for chapter_id, _ in chapters:
                    yield ConventionsRecord(chapter_id=chapter_id, stream=name, payload=conventions)


@dataclass(frozen=True)
class StageTypes:
    before: ActionType
    signature: ActionSignature
    after: ActionType

    @property
    def declared(self) -> Collection[str]:
        return self.signature.inputs.keys() | self.signature.optional_inputs.keys()


async def stage_types(db: AsyncSession, stage: TranslationStage) -> StageTypes:
    stages = (
        await db.scalars(
            select(TranslationStage)
            .where(TranslationStage.job_id == stage.job_id, TranslationStage.stage_num <= stage.stage_num)
            .order_by(TranslationStage.stage_num)
        )
    ).all()
    signatures = [stage_config(earlier.action, earlier.config).signature() for earlier in stages]
    states = infer_pipeline(signatures)
    return StageTypes(states[-2] if len(states) > 1 else {}, signatures[-1], states[-1])


async def resolve_inputs(
    context: ActionTaskContext, store: AsyncObjectStore, stage: TranslationStage, available: ActionType
) -> AsyncIterator[TranslationRecord]:
    if stage.stage_num == 0:
        return
    previous = (
        await context.db.execute(
            select(TranslationTask.status, TranslationTask.failed_at, TranslationTask.output_file_id)
            .join(TranslationStage, TranslationStage.stage_id == TranslationTask.stage_id)
            .where(
                TranslationTask.batch_id == context.task.batch_id,
                TranslationStage.job_id == stage.job_id,
                TranslationStage.stage_num == stage.stage_num - 1,
            )
        )
    ).one()
    if (
        previous.status != TranslationTaskStatus.COMPLETE
        or previous.failed_at is not None
        or previous.output_file_id is None
    ):
        raise ValueError("Previous translation task must have a completed output artifact")
    records = validate_output_records(
        aiter_translation_records(fetch_file(context.db, store, previous.output_file_id)),
        chapter_ids=await batch_chapter_ids(context, stage),
        output_type=available,
    )
    async for record in records:
        yield record


async def select_streams(
    records: AsyncIterable[TranslationRecord], streams: Collection[str]
) -> AsyncIterator[TranslationRecord]:
    async for record in records:
        if record.stream in streams:
            yield record


async def group_by_chapter(
    records: AsyncIterable[TranslationRecord], streams: Collection[str]
) -> AsyncIterator[dict[str, TranslationRecord]]:
    expected = frozenset(streams)
    pending: dict[UUID, dict[str, TranslationRecord]] = {}
    async for record in records:
        group = pending.setdefault(record.chapter_id, {})
        group[record.stream] = record
        if group.keys() == expected:
            yield pending.pop(record.chapter_id)
    if pending:
        chapter_id, group = next(iter(pending.items()))
        missing = ", ".join(sorted(expected - group.keys()))
        raise ValueError(f"Missing input streams for chapter {chapter_id}: {missing}")
