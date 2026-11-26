from collections import defaultdict
from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy import and_, func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.auth.models import User
from src.novels.models import Chapter, ChapterContent, Novel
from src.novels.permissions import (
    chapter_mod_access_insert,
    chapter_mod_access_select,
    novel_mod_access_select,
)
from src.translations.models import (
    TranslationBatch,
    TranslationChapterAccept,
    TranslationChapterOutput,
    TranslationJobChapter,
    TranslationStage,
)
from src.translations.schemas import (
    TranslationAcceptBatchScope,
    TranslationAcceptJobScope,
    TranslationAcceptRangeScope,
    TranslationAcceptRequest,
    TranslationAcceptResult,
    TranslationOutputChapterDetail,
    TranslationOutputChapterSummary,
    TranslationOutputsRead,
    TranslationStagedStage,
    TranslationTargetNovel,
)
from src.translations.service import TranslationNotFoundError, _job


class TranslationConflictError(Exception):
    pass


async def _staged_stages(db: AsyncSession, job_id: UUID) -> list[TranslationStagedStage]:
    rows = (
        (
            await db.execute(
                select(
                    TranslationStage.stage_id,
                    TranslationStage.stage_num,
                    TranslationStage.action,
                    func.count(TranslationChapterOutput.chapter_id).label("chapter_count"),
                )
                .join(TranslationChapterOutput, TranslationChapterOutput.stage_id == TranslationStage.stage_id)
                .where(TranslationStage.job_id == job_id)
                .group_by(TranslationStage.stage_id, TranslationStage.stage_num, TranslationStage.action)
                .order_by(TranslationStage.stage_num)
            )
        )
        .mappings()
        .all()
    )
    return [TranslationStagedStage.model_validate(row) for row in rows]


async def _validate_job_stage(db: AsyncSession, job_id: UUID, stage_id: UUID) -> UUID:
    found = await db.scalar(
        select(TranslationStage.stage_id).where(
            TranslationStage.job_id == job_id,
            TranslationStage.stage_id == stage_id,
        )
    )
    if found is None:
        raise TranslationNotFoundError("Translation stage not found")
    return found


async def list_translation_outputs(
    db: AsyncSession, user: User, job_id: UUID, *, stage_id: UUID | None = None
) -> TranslationOutputsRead:
    job = await _job(db, user, job_id)
    source_work_id = await db.scalar(select(Novel.source_work_id).where(Novel.novel_id == job.novel_id))
    if source_work_id is None:
        raise TranslationNotFoundError("Translation job novel not found")

    stages = await _staged_stages(db, job_id)
    selected_stage_id = (
        await _validate_job_stage(db, job_id, stage_id)
        if stage_id is not None
        else (stages[-1].stage_id if stages else None)
    )

    rows = (
        (
            await db.execute(
                select(
                    TranslationChapterOutput.chapter_id,
                    TranslationJobChapter.chapter_num,
                    Chapter.chapter_title,
                    TranslationJobChapter.batch_id,
                    TranslationBatch.batch_num,
                    TranslationChapterOutput.updated_at.label("staged_at"),
                )
                .join(
                    TranslationJobChapter,
                    and_(
                        TranslationJobChapter.job_id == TranslationChapterOutput.job_id,
                        TranslationJobChapter.chapter_id == TranslationChapterOutput.chapter_id,
                    ),
                )
                .join(TranslationBatch, TranslationBatch.batch_id == TranslationJobChapter.batch_id)
                .join(Chapter, Chapter.chapter_id == TranslationChapterOutput.chapter_id)
                .where(
                    TranslationChapterOutput.job_id == job_id,
                    TranslationChapterOutput.stage_id == selected_stage_id,
                )
                .order_by(TranslationJobChapter.chapter_num, TranslationChapterOutput.chapter_id)
            )
        )
        .mappings()
        .all()
        if selected_stage_id is not None
        else []
    )

    accepted_by_chapter: dict[UUID, list[UUID]] = defaultdict(list)
    if selected_stage_id is not None:
        target_chapter = aliased(Chapter)
        accept_rows = (
            await db.execute(
                select(
                    TranslationChapterAccept.source_chapter_id,
                    target_chapter.novel_id,
                )
                .join(
                    ChapterContent,
                    ChapterContent.chapter_content_id == TranslationChapterAccept.target_chapter_content_id,
                )
                .join(target_chapter, target_chapter.chapter_id == ChapterContent.chapter_id)
                .where(TranslationChapterAccept.stage_id == selected_stage_id)
                .group_by(
                    TranslationChapterAccept.source_chapter_id,
                    target_chapter.novel_id,
                )
                .order_by(
                    func.max(TranslationChapterAccept.created_at).desc(),
                    target_chapter.novel_id,
                )
            )
        ).all()
        for source_chapter_id, target_novel_id in accept_rows:
            accepted_by_chapter[source_chapter_id].append(target_novel_id)

    target_novel_rows = list(
        await db.scalars(
            novel_mod_access_select(
                select(Novel)
                .where(
                    Novel.source_work_id == source_work_id,
                    Novel.novel_id != job.novel_id,
                )
                .order_by(Novel.novel_title, Novel.novel_id),
                user,
                edit_only=True,
            )
        )
    )
    target_novels = [TranslationTargetNovel.model_validate(novel) for novel in target_novel_rows]
    target_novel_ids = {novel.novel_id for novel in target_novels}

    last_target_chapter = aliased(Chapter)
    last_accepted = await db.scalar(
        select(last_target_chapter.novel_id)
        .select_from(TranslationChapterAccept)
        .join(TranslationStage, TranslationStage.stage_id == TranslationChapterAccept.stage_id)
        .join(
            ChapterContent,
            ChapterContent.chapter_content_id == TranslationChapterAccept.target_chapter_content_id,
        )
        .join(last_target_chapter, last_target_chapter.chapter_id == ChapterContent.chapter_id)
        .where(TranslationStage.job_id == job_id)
        .order_by(TranslationChapterAccept.created_at.desc(), TranslationChapterAccept.accept_id.desc())
        .limit(1)
    )
    last_target_novel_id = last_accepted if last_accepted in target_novel_ids else None

    return TranslationOutputsRead(
        selected_stage_id=selected_stage_id,
        stages=stages,
        items=[
            TranslationOutputChapterSummary(
                chapter_id=row["chapter_id"],
                chapter_num=row["chapter_num"],
                chapter_title=row["chapter_title"],
                batch_id=row["batch_id"],
                batch_num=row["batch_num"],
                staged_at=row["staged_at"],
                accepted_novel_ids=accepted_by_chapter.get(row["chapter_id"], []),
            )
            for row in rows
        ],
        target_novels=target_novels,
        last_target_novel_id=last_target_novel_id,
    )


async def read_translation_output(
    db: AsyncSession, user: User, job_id: UUID, chapter_id: UUID, *, stage_id: UUID | None = None
) -> TranslationOutputChapterDetail:
    await _job(db, user, job_id)
    query = (
        select(
            TranslationChapterOutput.stage_id,
            TranslationStage.stage_num,
            TranslationChapterOutput.chapter_id,
            TranslationJobChapter.chapter_num,
            Chapter.chapter_title,
            TranslationJobChapter.batch_id,
            TranslationBatch.batch_num,
            TranslationJobChapter.source_chapter_content_id,
            ChapterContent.chapter_content_text.label("source_text"),
            TranslationChapterOutput.translated_text,
            TranslationChapterOutput.updated_at.label("staged_at"),
        )
        .join(TranslationStage, TranslationStage.stage_id == TranslationChapterOutput.stage_id)
        .join(
            TranslationJobChapter,
            and_(
                TranslationJobChapter.job_id == TranslationChapterOutput.job_id,
                TranslationJobChapter.chapter_id == TranslationChapterOutput.chapter_id,
            ),
        )
        .join(TranslationBatch, TranslationBatch.batch_id == TranslationJobChapter.batch_id)
        .join(Chapter, Chapter.chapter_id == TranslationChapterOutput.chapter_id)
        .join(
            ChapterContent,
            ChapterContent.chapter_content_id == TranslationJobChapter.source_chapter_content_id,
        )
        .where(
            TranslationChapterOutput.job_id == job_id,
            TranslationChapterOutput.chapter_id == chapter_id,
        )
    )
    if stage_id is not None:
        query = query.where(TranslationChapterOutput.stage_id == stage_id)
    else:
        query = query.order_by(TranslationStage.stage_num.desc()).limit(1)

    row = (await db.execute(query)).mappings().one_or_none()
    if row is None:
        raise TranslationNotFoundError("Staged chapter output not found")
    return TranslationOutputChapterDetail.model_validate(row)


async def accept_translation_outputs(
    db: AsyncSession,
    user: User,
    job_id: UUID,
    request: TranslationAcceptRequest,
) -> TranslationAcceptResult:
    job = await _job(db, user, job_id)
    target_novel = await db.scalar(
        novel_mod_access_select(
            select(Novel).where(Novel.novel_id == request.target_novel_id),
            user,
            edit_only=True,
        )
    )
    if target_novel is None:
        raise TranslationNotFoundError("Target novel not found")
    if target_novel.novel_id == job.novel_id:
        raise ValueError("Target novel cannot be the job's source novel")

    source_work_id = await db.scalar(select(Novel.source_work_id).where(Novel.novel_id == job.novel_id))
    if source_work_id is None or target_novel.source_work_id != source_work_id:
        raise ValueError("Target novel must belong to the same source work")

    if request.stage_id is not None:
        selected_stage_id = await _validate_job_stage(db, job_id, request.stage_id)
    else:
        stages = await _staged_stages(db, job_id)
        if not stages:
            raise ValueError("No staged translated chapters match the selected scope.")
        selected_stage_id = stages[-1].stage_id

    scope_filters = [
        TranslationChapterOutput.job_id == job_id,
        TranslationChapterOutput.stage_id == selected_stage_id,
    ]
    match request.scope:
        case TranslationAcceptJobScope():
            pass
        case TranslationAcceptBatchScope(batch_id=batch_id):
            scope_filters.append(TranslationJobChapter.batch_id == batch_id)
        case TranslationAcceptRangeScope(start_chapter_num=start, end_chapter_num=end):
            scope_filters.extend(
                [
                    TranslationJobChapter.chapter_num >= start,
                    TranslationJobChapter.chapter_num <= end,
                ]
            )

    matched_count = (
        await db.scalar(
            select(func.count())
            .select_from(TranslationChapterOutput)
            .join(
                TranslationJobChapter,
                and_(
                    TranslationJobChapter.job_id == TranslationChapterOutput.job_id,
                    TranslationJobChapter.chapter_id == TranslationChapterOutput.chapter_id,
                ),
            )
            .where(*scope_filters)
        )
        or 0
    )
    if matched_count == 0:
        raise ValueError("No staged translated chapters match the selected scope.")

    src_chapter = aliased(Chapter)
    target_chapter = aliased(Chapter)

    try:
        insert_chapters_select = chapter_mod_access_insert(
            select(
                literal(target_novel.novel_id),
                TranslationJobChapter.chapter_num,
                src_chapter.chapter_title,
                literal(False),
                func.now(),
                func.now(),
            )
            .select_from(TranslationChapterOutput)
            .join(
                TranslationJobChapter,
                and_(
                    TranslationJobChapter.job_id == TranslationChapterOutput.job_id,
                    TranslationJobChapter.chapter_id == TranslationChapterOutput.chapter_id,
                ),
            )
            .join(src_chapter, src_chapter.chapter_id == TranslationChapterOutput.chapter_id)
            .where(*scope_filters),
            user,
            target_novel.novel_id,
        )
        created_rows = (
            await db.execute(
                pg_insert(Chapter)
                .from_select(
                    ["novel_id", "chapter_num", "chapter_title", "chapter_is_public", "created_at", "updated_at"],
                    insert_chapters_select,
                )
                .on_conflict_do_nothing(index_elements=[Chapter.chapter_num, Chapter.novel_id])
                .returning(Chapter.chapter_id, Chapter.chapter_num)
            )
        ).all()
        created_chapter_ids = [chapter_id for chapter_id, _ in created_rows]
        created_chapter_nums = {chapter_num for _, chapter_num in created_rows}

        inserted_content_ids: list[UUID] = []
        if request.on_existing == "overwrite" or created_chapter_ids:
            if request.on_existing == "skip":
                content_select = (
                    select(
                        target_chapter.chapter_id,
                        TranslationChapterOutput.translated_text,
                        literal(1),
                        func.now(),
                        func.now(),
                    )
                    .select_from(TranslationChapterOutput)
                    .join(
                        TranslationJobChapter,
                        and_(
                            TranslationJobChapter.job_id == TranslationChapterOutput.job_id,
                            TranslationJobChapter.chapter_id == TranslationChapterOutput.chapter_id,
                        ),
                    )
                    .join(
                        target_chapter,
                        and_(
                            target_chapter.novel_id == target_novel.novel_id,
                            target_chapter.chapter_num == TranslationJobChapter.chapter_num,
                        ),
                    )
                    .where(*scope_filters, target_chapter.chapter_id.in_(created_chapter_ids))
                )
            else:
                max_versions = (
                    select(
                        ChapterContent.chapter_id,
                        func.max(ChapterContent.chapter_content_version).label("max_version"),
                    )
                    .join(Chapter, Chapter.chapter_id == ChapterContent.chapter_id)
                    .where(Chapter.novel_id == target_novel.novel_id)
                    .group_by(ChapterContent.chapter_id)
                    .subquery()
                )
                content_select = (
                    select(
                        target_chapter.chapter_id,
                        TranslationChapterOutput.translated_text,
                        func.coalesce(max_versions.c.max_version, 0) + 1,
                        func.now(),
                        func.now(),
                    )
                    .select_from(TranslationChapterOutput)
                    .join(
                        TranslationJobChapter,
                        and_(
                            TranslationJobChapter.job_id == TranslationChapterOutput.job_id,
                            TranslationJobChapter.chapter_id == TranslationChapterOutput.chapter_id,
                        ),
                    )
                    .join(
                        target_chapter,
                        and_(
                            target_chapter.novel_id == target_novel.novel_id,
                            target_chapter.chapter_num == TranslationJobChapter.chapter_num,
                        ),
                    )
                    .outerjoin(max_versions, max_versions.c.chapter_id == target_chapter.chapter_id)
                    .where(*scope_filters)
                )

            content_select = chapter_mod_access_select(content_select, user, target_chapter, edit_only=True)
            inserted_content_ids = list(
                await db.scalars(
                    pg_insert(ChapterContent)
                    .from_select(
                        ["chapter_id", "chapter_content_text", "chapter_content_version", "created_at", "updated_at"],
                        content_select,
                    )
                    .returning(ChapterContent.chapter_content_id)
                )
            )

        written_chapter_nums: list[int] = []
        if inserted_content_ids:
            accept_select = (
                select(
                    literal(selected_stage_id),
                    TranslationChapterOutput.chapter_id,
                    ChapterContent.chapter_content_id,
                    func.now(),
                    func.now(),
                )
                .select_from(ChapterContent)
                .join(target_chapter, target_chapter.chapter_id == ChapterContent.chapter_id)
                .join(
                    TranslationJobChapter,
                    and_(
                        TranslationJobChapter.job_id == job_id,
                        TranslationJobChapter.chapter_num == target_chapter.chapter_num,
                    ),
                )
                .join(
                    TranslationChapterOutput,
                    and_(
                        TranslationChapterOutput.stage_id == selected_stage_id,
                        TranslationChapterOutput.chapter_id == TranslationJobChapter.chapter_id,
                    ),
                )
                .where(ChapterContent.chapter_content_id.in_(inserted_content_ids))
            )
            await db.execute(
                pg_insert(TranslationChapterAccept).from_select(
                    ["stage_id", "source_chapter_id", "target_chapter_content_id", "created_at", "updated_at"],
                    accept_select,
                )
            )
            written_chapter_nums = list(
                await db.scalars(
                    select(Chapter.chapter_num)
                    .join(ChapterContent, ChapterContent.chapter_id == Chapter.chapter_id)
                    .where(ChapterContent.chapter_content_id.in_(inserted_content_ids))
                    .order_by(Chapter.chapter_num)
                )
            )

        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, UniqueViolation):
            raise TranslationConflictError("Concurrent update conflict while accepting translation outputs") from error
        raise
    except Exception:
        await db.rollback()
        raise

    created_chapters = sum(1 for num in written_chapter_nums if num in created_chapter_nums)
    updated_chapters = len(written_chapter_nums) - created_chapters
    skipped_chapters = matched_count - len(written_chapter_nums)

    return TranslationAcceptResult(
        target_novel_id=target_novel.novel_id,
        created_chapters=created_chapters,
        updated_chapters=updated_chapters,
        skipped_chapters=skipped_chapters,
        chapter_nums=written_chapter_nums,
    )
