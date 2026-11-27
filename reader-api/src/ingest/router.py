import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_partner
from src.config import novel_public_url, reader_settings
from src.database import get_async_db
from src.models import ReaderChapter, ReaderNovel, ReaderPartner
from src.schemas import (
    IngestChaptersDeleteRequest,
    IngestChaptersDeleteResponse,
    IngestChapterStatus,
    IngestChaptersUpsertRequest,
    IngestChaptersUpsertResponse,
    IngestHealthResponse,
    IngestNovelStatusResponse,
    IngestNovelUpsertRequest,
    IngestNovelUpsertResponse,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])

ExternalIdPath = Annotated[str, Path(alias="externalId", min_length=1, max_length=128)]


def _hash_body(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


async def _get_partner_novel(
    db: AsyncSession, partner: ReaderPartner, external_id: str
) -> ReaderNovel | None:
    stmt = select(ReaderNovel).where(
        ReaderNovel.partner_id == partner.partner_id,
        ReaderNovel.external_id == external_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


@router.get("/health", response_model=IngestHealthResponse, operation_id="ingest_health")
async def ingest_health(
    _partner: Annotated[ReaderPartner, Depends(require_partner)],
) -> IngestHealthResponse:
    return IngestHealthResponse(
        ok=True,
        protocol_version=1,
        name=reader_settings.READER_INSTANCE_NAME,
        public_base_url=reader_settings.normalized_public_base_url,
    )


@router.get(
    "/novels/{externalId}/status",
    response_model=IngestNovelStatusResponse,
    operation_id="ingest_novel_status",
)
async def ingest_novel_status(
    external_id: ExternalIdPath,
    partner: Annotated[ReaderPartner, Depends(require_partner)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> IngestNovelStatusResponse:
    novel = await _get_partner_novel(db, partner, external_id)
    if novel is None:
        return IngestNovelStatusResponse(exists=False, novel_id=None, public_url=None, chapters=[])

    chapter_stmt = (
        select(
            ReaderChapter.chapter_num,
            ReaderChapter.title,
            ReaderChapter.content_hash,
            ReaderChapter.external_version,
            ReaderChapter.updated_at,
        )
        .where(ReaderChapter.novel_id == novel.novel_id)
        .order_by(ReaderChapter.chapter_num.asc())
    )
    rows = (await db.execute(chapter_stmt)).all()
    return IngestNovelStatusResponse(
        exists=True,
        novel_id=novel.novel_id,
        public_url=novel_public_url(novel.novel_id),
        chapters=[
            IngestChapterStatus(
                chapter_num=row.chapter_num,
                title=row.title,
                content_hash=row.content_hash,
                external_version=row.external_version,
                updated_at=row.updated_at,
            )
            for row in rows
        ],
    )


@router.put(
    "/novels/{externalId}",
    response_model=IngestNovelUpsertResponse,
    operation_id="ingest_upsert_novel",
)
async def ingest_upsert_novel(
    external_id: ExternalIdPath,
    payload: IngestNovelUpsertRequest,
    partner: Annotated[ReaderPartner, Depends(require_partner)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> IngestNovelUpsertResponse:
    insert_stmt = pg_insert(ReaderNovel).values(
        partner_id=partner.partner_id,
        external_id=external_id,
        title=payload.title,
        description=payload.description,
        author=payload.author,
        language_code=payload.language_code,
        toc_version=1,
    )
    upsert_stmt = insert_stmt.on_conflict_do_update(
        constraint="uq_reader_novels_partner_external_id",
        set_={
            "title": insert_stmt.excluded.title,
            "description": insert_stmt.excluded.description,
            "author": insert_stmt.excluded.author,
            "language_code": insert_stmt.excluded.language_code,
            "toc_version": ReaderNovel.toc_version + 1,
            "updated_at": func.now(),
        },
    ).returning(ReaderNovel.novel_id)

    novel_id = (await db.execute(upsert_stmt)).scalar_one()
    await db.commit()
    return IngestNovelUpsertResponse(novel_id=novel_id, public_url=novel_public_url(novel_id))


@router.put(
    "/novels/{externalId}/chapters",
    response_model=IngestChaptersUpsertResponse,
    operation_id="ingest_upsert_chapters",
)
async def ingest_upsert_chapters(
    external_id: ExternalIdPath,
    payload: IngestChaptersUpsertRequest,
    partner: Annotated[ReaderPartner, Depends(require_partner)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> IngestChaptersUpsertResponse:
    novel = await _get_partner_novel(db, partner, external_id)
    if novel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel not found; create it with PUT /ingest/novels/{externalId} first",
        )

    if not payload.chapters:
        return IngestChaptersUpsertResponse(
            novel_id=novel.novel_id,
            public_url=novel_public_url(novel.novel_id),
            upserted_chapter_nums=[],
        )

    deduped = {item.chapter_num: item for item in payload.chapters}
    rows = [
        {
            "novel_id": novel.novel_id,
            "chapter_num": item.chapter_num,
            "title": item.title,
            "body": item.body,
            "content_hash": _hash_body(item.body),
            "external_version": item.external_version,
        }
        for item in deduped.values()
    ]

    insert_stmt = pg_insert(ReaderChapter).values(rows)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        constraint="uq_reader_chapters_novel_chapter_num",
        set_={
            "title": insert_stmt.excluded.title,
            "body": insert_stmt.excluded.body,
            "content_hash": insert_stmt.excluded.content_hash,
            "external_version": insert_stmt.excluded.external_version,
            "updated_at": func.now(),
        },
    )
    await db.execute(upsert_stmt)
    await db.execute(
        update(ReaderNovel)
        .where(ReaderNovel.novel_id == novel.novel_id)
        .values(toc_version=ReaderNovel.toc_version + 1, updated_at=func.now())
    )
    await db.commit()

    return IngestChaptersUpsertResponse(
        novel_id=novel.novel_id,
        public_url=novel_public_url(novel.novel_id),
        upserted_chapter_nums=sorted(deduped.keys()),
    )


@router.delete(
    "/novels/{externalId}/chapters",
    response_model=IngestChaptersDeleteResponse,
    operation_id="ingest_delete_chapters",
)
async def ingest_delete_chapters(
    external_id: ExternalIdPath,
    payload: IngestChaptersDeleteRequest,
    partner: Annotated[ReaderPartner, Depends(require_partner)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> IngestChaptersDeleteResponse:
    novel = await _get_partner_novel(db, partner, external_id)
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")

    unique_nums = sorted(set(payload.chapter_nums))
    if not unique_nums:
        return IngestChaptersDeleteResponse(deleted_chapter_nums=[])

    delete_stmt = (
        delete(ReaderChapter)
        .where(
            ReaderChapter.novel_id == novel.novel_id,
            ReaderChapter.chapter_num.in_(unique_nums),
        )
        .returning(ReaderChapter.chapter_num)
    )
    deleted_nums = sorted((await db.execute(delete_stmt)).scalars().all())
    if deleted_nums:
        await db.execute(
            update(ReaderNovel)
            .where(ReaderNovel.novel_id == novel.novel_id)
            .values(toc_version=ReaderNovel.toc_version + 1, updated_at=func.now())
        )
    await db.commit()

    return IngestChaptersDeleteResponse(deleted_chapter_nums=deleted_nums)
