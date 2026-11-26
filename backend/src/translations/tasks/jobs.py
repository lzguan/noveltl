from uuid import UUID

from sqlalchemy import Integer, case, cast, func, insert, literal, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from src.novels.models import Chapter, ChapterContent
from src.translations.models import (
    TranslationBatch,
    TranslationJob,
    TranslationJobChapter,
    TranslationStage,
    TranslationTask,
)
from src.translations.schemas import TranslationJobCreate
from src.translations.types import TranslationTaskStatus


async def create_job(db: AsyncSession, request: TranslationJobCreate) -> UUID:
    """Create a translation job and its complete stage-by-batch execution graph."""
    latest_content_version = (
        select(func.max(ChapterContent.chapter_content_version))
        .where(ChapterContent.chapter_id == Chapter.chapter_id)
        .correlate(Chapter)
        .scalar_subquery()
    )
    batch_num = cast(
        func.floor(
            (func.row_number().over(order_by=(Chapter.chapter_num, Chapter.chapter_id)) - 1) / request.config.batch_size
        ),
        Integer,
    ).label("batch_num")
    selected_chapters_statement = (
        select(Chapter.chapter_id, Chapter.chapter_num, ChapterContent.chapter_content_id, batch_num)
        .join(ChapterContent, ChapterContent.chapter_id == Chapter.chapter_id)
        .where(
            Chapter.novel_id == request.novel_id,
            ChapterContent.chapter_content_version == latest_content_version,
        )
    )
    if request.config.start_chapter_num is not None:
        selected_chapters_statement = selected_chapters_statement.where(
            Chapter.chapter_num >= request.config.start_chapter_num
        )
    if request.config.end_chapter_num is not None:
        selected_chapters_statement = selected_chapters_statement.where(
            Chapter.chapter_num < request.config.end_chapter_num
        )
    selected_chapters = selected_chapters_statement.cte("selected_chapters").prefix_with("MATERIALIZED")

    try:
        job_id = (
            await db.execute(
                insert(TranslationJob)
                .values(
                    novel_id=request.novel_id,
                    config=request.config.model_dump(mode="json"),
                )
                .returning(TranslationJob.job_id)
            )
        ).scalar_one()

        await db.execute(
            insert(TranslationStage),
            [
                {
                    "job_id": job_id,
                    "stage_num": stage_num,
                    "action": stage.action,
                    "config": stage.model_dump(mode="json")["config"],
                }
                for stage_num, stage in enumerate(request.stages, start=1)
            ]
            + [
                {
                    "job_id": job_id,
                    "stage_num": 0,
                    "action": "load_inputs",
                    "config": request.loader_config().model_dump(mode="json"),
                }
            ],
        )

        inserted_batches = (
            insert(TranslationBatch)
            .from_select(
                ["job_id", "batch_num"],
                select(literal(job_id), selected_chapters.c.batch_num).distinct(),
            )
            .returning(TranslationBatch.batch_id, TranslationBatch.batch_num)
            .cte("inserted_batches")
        )
        await db.execute(
            insert(TranslationJobChapter).from_select(
                [
                    "job_id",
                    "chapter_id",
                    "source_chapter_content_id",
                    "batch_id",
                    "chapter_num",
                ],
                select(
                    literal(job_id),
                    selected_chapters.c.chapter_id,
                    selected_chapters.c.chapter_content_id,
                    inserted_batches.c.batch_id,
                    selected_chapters.c.chapter_num,
                ).join(
                    inserted_batches,
                    inserted_batches.c.batch_num == selected_chapters.c.batch_num,
                ),
            )
        )

        task_status = case(
            (TranslationStage.stage_num == 0, literal(TranslationTaskStatus.READY.value)),
            else_=literal(TranslationTaskStatus.WAITING.value),
        )
        await db.execute(
            insert(TranslationTask).from_select(
                ["stage_id", "batch_id", "status"],
                select(
                    TranslationStage.stage_id,
                    TranslationBatch.batch_id,
                    task_status,
                )
                .select_from(TranslationStage)
                .join(TranslationBatch, true())
                .where(
                    TranslationStage.job_id == job_id,
                    TranslationBatch.job_id == job_id,
                ),
            )
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return job_id
