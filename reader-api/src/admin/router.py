import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.admin.auth import create_admin_token, require_admin, verify_admin_credentials
from src.auth import generate_api_key
from src.config import novel_public_url, reader_settings
from src.database import get_async_db
from src.models import ReaderChapter, ReaderNovel, ReaderPartner, ReaderPartnerKey
from src.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMintKeyResponse,
    AdminNovelSummary,
    AdminPartnerCreateRequest,
    AdminPartnerCreateResponse,
    AdminPartnerKeySummary,
    AdminPartnerSummary,
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
