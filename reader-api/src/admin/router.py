import base64
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.admin.auth import create_admin_token, require_admin, verify_admin_credentials
from src.auth import generate_api_key
from src.config import novel_public_url, reader_settings
from src.database import get_async_db
from src.models import ReaderChapter, ReaderFeedback, ReaderNovel, ReaderPartner, ReaderPartnerKey
from src.schemas import (
    AdminFeedbackItem,
    AdminFeedbackListResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMintKeyResponse,
    AdminNovelSummary,
    AdminPartnerCreateRequest,
    AdminPartnerCreateResponse,
    AdminPartnerKeySummary,
    AdminPartnerSummary,
    FeedbackKind,
)

router = APIRouter(prefix="/admin", tags=["admin"])

PartnerIdPath = Annotated[uuid.UUID, Path(alias="partnerId")]
KeyIdPath = Annotated[uuid.UUID, Path(alias="keyId")]
NovelIdPath = Annotated[uuid.UUID, Path(alias="novelId")]
ChapterNumPath = Annotated[int, Path(alias="chapterNum", ge=0)]


@router.post("/login", response_model=AdminLoginResponse, operation_id="admin_login")
async def admin_login(payload: AdminLoginRequest) -> AdminLoginResponse:
    if not reader_settings.is_admin_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reader admin is not configured",
        )
    if not verify_admin_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )
    access_token, expires_at = create_admin_token(reader_settings.READER_ADMIN_USERNAME)
    return AdminLoginResponse(access_token=access_token, expires_at=expires_at)


@router.get("/partners", response_model=list[AdminPartnerSummary], operation_id="admin_list_partners")
async def admin_list_partners(
    _admin: Annotated[str, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[AdminPartnerSummary]:
    partners_stmt = (
        select(ReaderPartner)
        .options(selectinload(ReaderPartner.keys))
        .order_by(ReaderPartner.created_at.asc(), ReaderPartner.partner_id.asc())
    )
    partners = (await db.execute(partners_stmt)).scalars().all()

    novel_counts_stmt = (
        select(ReaderNovel.partner_id, func.count(ReaderNovel.novel_id))
        .where(ReaderNovel.partner_id.is_not(None))
        .group_by(ReaderNovel.partner_id)
    )
    counts_by_partner = {
        partner_id: count
        for partner_id, count in (await db.execute(novel_counts_stmt)).all()
        if partner_id is not None
    }

    result: list[AdminPartnerSummary] = []
    for partner in partners:
        sorted_keys = sorted(partner.keys, key=lambda key: (key.created_at, str(key.key_id)))
        result.append(
            AdminPartnerSummary(
                partner_id=partner.partner_id,
                name=partner.name,
                created_at=partner.created_at,
                novel_count=counts_by_partner.get(partner.partner_id, 0),
                keys=[
                    AdminPartnerKeySummary(
                        key_id=key.key_id,
                        key_prefix=key.key_prefix,
                        created_at=key.created_at,
                        revoked_at=key.revoked_at,
                    )
                    for key in sorted_keys
                ],
            )
        )
    return result


@router.post(
    "/partners",
    response_model=AdminPartnerCreateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_create_partner",
)
async def admin_create_partner(
    payload: AdminPartnerCreateRequest,
    _admin: Annotated[str, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> AdminPartnerCreateResponse:
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Partner name must not be blank",
        )
    partner = ReaderPartner(name=name)
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    return AdminPartnerCreateResponse(
        partner_id=partner.partner_id,
        name=partner.name,
        created_at=partner.created_at,
    )


@router.post(
    "/partners/{partnerId}/keys",
    response_model=AdminMintKeyResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_mint_partner_key",
)
async def admin_mint_partner_key(
    partner_id: PartnerIdPath,
    _admin: Annotated[str, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> AdminMintKeyResponse:
    partner = (
        await db.execute(select(ReaderPartner).where(ReaderPartner.partner_id == partner_id))
    ).scalar_one_or_none()
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")

    raw_key, key_prefix, key_hash = generate_api_key()
    key = ReaderPartnerKey(
        partner_id=partner.partner_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return AdminMintKeyResponse(
        key_id=key.key_id,
        key_prefix=key.key_prefix,
        api_key=raw_key,
        created_at=key.created_at,
    )


@router.delete(
    "/keys/{keyId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="admin_revoke_key",
)
async def admin_revoke_key(
    key_id: KeyIdPath,
    _admin: Annotated[str, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Response:
    key = (
        await db.execute(select(ReaderPartnerKey).where(ReaderPartnerKey.key_id == key_id))
    ).scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")

    if key.revoked_at is None:
        await db.execute(
            update(ReaderPartnerKey)
            .where(ReaderPartnerKey.key_id == key_id, ReaderPartnerKey.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/novels", response_model=list[AdminNovelSummary], operation_id="admin_list_novels")
async def admin_list_novels(
    _admin: Annotated[str, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[AdminNovelSummary]:
    chapter_counts_subq = (
        select(
            ReaderChapter.novel_id.label("novel_id"),
            func.count(ReaderChapter.chapter_id).label("chapter_count"),
        )
        .group_by(ReaderChapter.novel_id)
        .subquery()
    )
    stmt = (
        select(
            ReaderNovel.novel_id,
            ReaderNovel.title,
            ReaderNovel.author,
            ReaderNovel.language_code,
            ReaderNovel.partner_id,
            ReaderPartner.name.label("partner_name"),
            func.coalesce(chapter_counts_subq.c.chapter_count, 0).label("chapter_count"),
            ReaderNovel.updated_at,
        )
        .outerjoin(ReaderPartner, ReaderNovel.partner_id == ReaderPartner.partner_id)
        .outerjoin(chapter_counts_subq, ReaderNovel.novel_id == chapter_counts_subq.c.novel_id)
        .order_by(ReaderNovel.updated_at.desc(), ReaderNovel.novel_id.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        AdminNovelSummary(
            novel_id=row.novel_id,
            title=row.title,
            author=row.author,
            language_code=row.language_code,
            partner_id=row.partner_id,
            partner_name=row.partner_name,
            chapter_count=int(row.chapter_count),
            updated_at=row.updated_at,
            public_url=novel_public_url(row.novel_id),
        )
        for row in rows
    ]


@router.delete(
    "/novels/{novelId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="admin_delete_novel",
)
async def admin_delete_novel(
    novel_id: NovelIdPath,
    _admin: Annotated[str, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Response:
    deleted_id = (
        await db.execute(
            delete(ReaderNovel)
            .where(ReaderNovel.novel_id == novel_id)
            .returning(ReaderNovel.novel_id)
        )
    ).scalar_one_or_none()
    if deleted_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/novels/{novelId}/chapters/{chapterNum}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="admin_delete_chapter",
)
async def admin_delete_chapter(
    novel_id: NovelIdPath,
    chapter_num: ChapterNumPath,
    _admin: Annotated[str, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> Response:
    deleted_id = (
        await db.execute(
            delete(ReaderChapter)
            .where(
                ReaderChapter.novel_id == novel_id,
                ReaderChapter.chapter_num == chapter_num,
            )
            .returning(ReaderChapter.chapter_id)
        )
    ).scalar_one_or_none()
    if deleted_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    await db.execute(
        update(ReaderNovel)
        .where(ReaderNovel.novel_id == novel_id)
        .values(toc_version=ReaderNovel.toc_version + 1, updated_at=func.now())
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


EXPORT_BATCH_SIZE = 500


def _encode_feedback_cursor(created_at: datetime, feedback_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{feedback_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_feedback_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode()
        ts_part, id_part = decoded.split("|", 1)
        parsed_ts = datetime.fromisoformat(ts_part)
        if parsed_ts.tzinfo is None:
            parsed_ts = parsed_ts.replace(tzinfo=UTC)
        parsed_id = uuid.UUID(id_part)
        return parsed_ts, parsed_id
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid pagination cursor",
        ) from exc


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


@router.get(
    "/feedback",
    response_model=AdminFeedbackListResponse,
    operation_id="admin_list_feedback",
)
async def admin_list_feedback(
    _admin: Annotated[str, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    novel_id: Annotated[uuid.UUID | None, Query(alias="novelId")] = None,
    kind: Annotated[FeedbackKind | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before: Annotated[str | None, Query()] = None,
) -> AdminFeedbackListResponse:
    stmt = select(
        ReaderFeedback.feedback_id,
        ReaderFeedback.novel_id,
        ReaderNovel.title.label("novel_title"),
        ReaderFeedback.chapter_id,
        ReaderFeedback.chapter_num,
        ReaderFeedback.content_hash,
        ReaderFeedback.external_version,
        ReaderFeedback.kind,
        ReaderFeedback.payload,
        ReaderFeedback.client_hash,
        ReaderFeedback.created_at,
    ).join(ReaderNovel, ReaderFeedback.novel_id == ReaderNovel.novel_id)

    if novel_id is not None:
        stmt = stmt.where(ReaderFeedback.novel_id == novel_id)
    if kind is not None:
        stmt = stmt.where(ReaderFeedback.kind == kind)
    if before is not None:
        cursor_ts, cursor_id = _decode_feedback_cursor(before)
        stmt = stmt.where(tuple_(ReaderFeedback.created_at, ReaderFeedback.feedback_id) < (cursor_ts, cursor_id))

    stmt = stmt.order_by(ReaderFeedback.created_at.desc(), ReaderFeedback.feedback_id.desc()).limit(limit + 1)
    rows = (await db.execute(stmt)).all()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = (
        _encode_feedback_cursor(page_rows[-1].created_at, page_rows[-1].feedback_id)
        if has_more and page_rows
        else None
    )

    items = [
        AdminFeedbackItem(
            feedback_id=row.feedback_id,
            novel_id=row.novel_id,
            novel_title=row.novel_title,
            chapter_id=row.chapter_id,
            chapter_num=row.chapter_num,
            content_hash=row.content_hash,
            external_version=row.external_version,
            kind=row.kind,
            payload=row.payload,
            client_hash=row.client_hash,
            created_at=row.created_at,
        )
        for row in page_rows
    ]
    return AdminFeedbackListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/feedback/export",
    operation_id="admin_export_feedback",
    responses={
        200: {
            "description": "Newline-delimited JSON feedback export",
            "content": {"application/x-ndjson": {}},
        }
    },
)
async def admin_export_feedback(
    _admin: Annotated[str, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
) -> StreamingResponse:
    if until is None:
        effective_until: datetime = (await db.execute(select(func.now()))).scalar_one()
    else:
        effective_until = _normalize_utc(until)
    effective_since = _normalize_utc(since) if since is not None else None

    async def _ndjson_stream() -> AsyncIterator[str]:
        last_cursor: tuple[datetime, uuid.UUID] | None = None
        while True:
            stmt = select(ReaderFeedback).where(ReaderFeedback.created_at <= effective_until)
            if effective_since is not None:
                stmt = stmt.where(ReaderFeedback.created_at > effective_since)
            if last_cursor is not None:
                stmt = stmt.where(tuple_(ReaderFeedback.created_at, ReaderFeedback.feedback_id) > last_cursor)
            stmt = stmt.order_by(ReaderFeedback.created_at.asc(), ReaderFeedback.feedback_id.asc()).limit(
                EXPORT_BATCH_SIZE
            )
            batch = (await db.execute(stmt)).scalars().all()
            if not batch:
                break
            for row in batch:
                line = json.dumps(
                    {
                        "feedbackId": str(row.feedback_id),
                        "novelId": str(row.novel_id),
                        "chapterId": str(row.chapter_id),
                        "chapterNum": row.chapter_num,
                        "contentHash": row.content_hash,
                        "externalVersion": row.external_version,
                        "kind": row.kind,
                        "payload": row.payload,
                        "clientHash": row.client_hash,
                        "createdAt": row.created_at.isoformat(),
                    },
                    separators=(",", ":"),
                )
                yield f"{line}\n"
            if len(batch) < EXPORT_BATCH_SIZE:
                break
            last_row = batch[-1]
            last_cursor = (last_row.created_at, last_row.feedback_id)

    return StreamingResponse(
        _ndjson_stream(),
        media_type="application/x-ndjson",
        headers={
            "X-Export-Until": effective_until.isoformat(),
            "Cache-Control": "no-store",
        },
    )
