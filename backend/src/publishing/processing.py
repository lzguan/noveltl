import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import publishing_settings
from src.novels.models import Chapter, ChapterContent, Novel
from src.publishing.client import ReaderClient
from src.publishing.models import PublishingTarget, PublishJob
from src.publishing.reader_schemas import IngestChapterUpsertItem, IngestNovelUpsertRequest
from src.publishing.security import decrypt_api_key, validate_target_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _StudioChapterRow:
    chapter_num: int
    chapter_title: str
    chapter_content_id: uuid.UUID
    chapter_content_text: str


async def _load_studio_chapters(
    db: AsyncSession,
    novel_id: uuid.UUID,
    *,
    after_chapter_num: int | None = None,
    start_chapter: int | None = None,
    end_chapter: int | None = None,
) -> list[_StudioChapterRow]:
    latest_version_subq = (
        select(
            ChapterContent.chapter_id.label("chapter_id"),
            func.max(ChapterContent.chapter_content_version).label("max_version"),
        )
        .join(Chapter, Chapter.chapter_id == ChapterContent.chapter_id)
        .where(Chapter.novel_id == novel_id)
        .group_by(ChapterContent.chapter_id)
        .subquery()
    )
    stmt = (
        select(
            Chapter.chapter_num,
            Chapter.chapter_title,
            ChapterContent.chapter_content_id,
            ChapterContent.chapter_content_text,
        )
        .join(latest_version_subq, latest_version_subq.c.chapter_id == Chapter.chapter_id)
        .join(
            ChapterContent,
            and_(
                ChapterContent.chapter_id == latest_version_subq.c.chapter_id,
                ChapterContent.chapter_content_version == latest_version_subq.c.max_version,
            ),
        )
        .where(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_num.asc())
    )
    if after_chapter_num is not None:
        stmt = stmt.where(Chapter.chapter_num > after_chapter_num)
    if start_chapter is not None:
        stmt = stmt.where(Chapter.chapter_num >= start_chapter)
    if end_chapter is not None:
        stmt = stmt.where(Chapter.chapter_num <= end_chapter)

    rows = (await db.execute(stmt)).all()
    return [
        _StudioChapterRow(
            chapter_num=row.chapter_num,
            chapter_title=row.chapter_title,
            chapter_content_id=row.chapter_content_id,
            chapter_content_text=row.chapter_content_text,
        )
        for row in rows
    ]


async def process_publish_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    *,
    reader_client: ReaderClient | None = None,
    chunk_size: int | None = None,
) -> PublishJob | None:
    claim_stmt = (
        update(PublishJob)
        .where(PublishJob.job_id == job_id, PublishJob.status == "pending")
        .values(status="processing", updated_at=func.now())
        .returning(PublishJob)
    )
    job = (await db.execute(claim_stmt)).scalar_one_or_none()
    await db.commit()
    if job is None:
        return None

    client = reader_client or ReaderClient()
    effective_chunk_size = chunk_size if chunk_size is not None else publishing_settings.PUBLISH_CHUNK_SIZE
    novel_id = job.novel_id
    target_id = job.target_id
    mode = job.mode
    start_chapter = job.start_chapter
    end_chapter = job.end_chapter
    include_novel_metadata = job.include_novel_metadata
    cursor_chapter_num = job.cursor_chapter_num
    synced_chapters = job.synced_chapters
    reader_novel_id = job.reader_novel_id
    public_url = job.public_url

    try:
        novel = (await db.execute(select(Novel).where(Novel.novel_id == novel_id))).scalar_one_or_none()
        if novel is None:
            raise ValueError(f"Novel {novel_id} not found.")

        target = (
            await db.execute(select(PublishingTarget).where(PublishingTarget.target_id == target_id))
        ).scalar_one_or_none()
        if target is None:
            raise ValueError(f"Publishing target {target_id} not found.")

        api_base_url = await validate_target_url(target.api_base_url)
        api_key = decrypt_api_key(target.encrypted_api_key)
        external_id = str(novel.novel_id)

        chapters = await _load_studio_chapters(
            db,
            novel_id,
            after_chapter_num=cursor_chapter_num,
            start_chapter=start_chapter if mode == "range" else None,
            end_chapter=end_chapter if mode == "range" else None,
        )

        if mode == "outdated":
            reader_status = await client.get_novel_status(api_base_url, api_key, external_id)
            if reader_status.exists:
                reader_novel_id = reader_status.novel_id
                public_url = reader_status.public_url
            reader_versions = {ch.chapter_num: ch.external_version for ch in (reader_status.chapters or [])}
            chapters = [
                ch
                for ch in chapters
                if ch.chapter_num not in reader_versions
                or reader_versions[ch.chapter_num] != str(ch.chapter_content_id)
            ]

        total_chapters = synced_chapters + len(chapters)
        await db.execute(
            update(PublishJob)
            .where(PublishJob.job_id == job_id)
            .values(
                total_chapters=total_chapters,
                reader_novel_id=reader_novel_id,
                public_url=public_url,
                updated_at=func.now(),
            )
        )
        await db.commit()

        novel_payload = IngestNovelUpsertRequest(
            title=novel.novel_title,
            description=novel.novel_description,
            author=novel.novel_author,
            language_code=novel.language_code,
        )

        if not chapters:
            if include_novel_metadata:
                sync_result = await client.sync_novel(
                    api_base_url,
                    api_key,
                    external_id,
                    novel=novel_payload,
                    upserts=[],
                )
                reader_novel_id = sync_result.novel_id
                public_url = sync_result.public_url
        else:
            for offset in range(0, len(chapters), effective_chunk_size):
                chunk = chapters[offset : offset + effective_chunk_size]
                chunk_novel = novel_payload if (offset == 0 and include_novel_metadata) else None
                upserts = [
                    IngestChapterUpsertItem(
                        chapter_num=ch.chapter_num,
                        title=ch.chapter_title,
                        body=ch.chapter_content_text,
                        external_version=str(ch.chapter_content_id),
                    )
                    for ch in chunk
                ]
                sync_result = await client.sync_novel(
                    api_base_url,
                    api_key,
                    external_id,
                    novel=chunk_novel,
                    upserts=upserts,
                )
                cursor_chapter_num = chunk[-1].chapter_num
                synced_chapters += len(chunk)
                reader_novel_id = sync_result.novel_id
                public_url = sync_result.public_url

                await db.execute(
                    update(PublishJob)
                    .where(PublishJob.job_id == job_id)
                    .values(
                        cursor_chapter_num=cursor_chapter_num,
                        synced_chapters=synced_chapters,
                        reader_novel_id=reader_novel_id,
                        public_url=public_url,
                        updated_at=func.now(),
                    )
                )
                await db.commit()

        completed_job = (
            await db.execute(
                update(PublishJob)
                .where(PublishJob.job_id == job_id)
                .values(
                    status="completed",
                    reader_novel_id=reader_novel_id,
                    public_url=public_url,
                    error_message=None,
                    completed_at=func.now(),
                    updated_at=func.now(),
                )
                .returning(PublishJob)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        await db.commit()
        return completed_job
    except Exception as error:
        logger.exception("Publish job failed job_id=%s", job_id)
        await db.rollback()
        failed_job = (
            await db.execute(
                update(PublishJob)
                .where(PublishJob.job_id == job_id)
                .values(
                    status="failed",
                    error_message=str(error)[:2000],
                    completed_at=func.now(),
                    updated_at=func.now(),
                )
                .returning(PublishJob)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        await db.commit()
        return failed_job
