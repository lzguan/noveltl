import hashlib
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.caching import apply_cache_headers, etag_matches, make_etag, not_modified_response
from src.config import reader_settings
from src.database import get_async_db
from src.models import ReaderChapter, ReaderFeedback, ReaderNovel
from src.schemas import (
    FeedbackCommentCreateRequest,
    FeedbackCreateRequest,
    FeedbackCreateResponse,
    FeedbackIssueCreateRequest,
    FeedbackReactionCreateRequest,
    PublicChapterDetail,
    PublicChapterNav,
    PublicChapterSummary,
    PublicNovelSummary,
)

router = APIRouter(tags=["public"])

NOVELS_CACHE_CONTROL = "public, max-age=0, s-maxage=60, stale-while-revalidate=300"
TOC_CACHE_CONTROL = "public, max-age=0, s-maxage=60, stale-while-revalidate=600"
CHAPTER_CACHE_CONTROL = "public, max-age=0, s-maxage=300, stale-while-revalidate=3600"

NovelIdPath = Annotated[uuid.UUID, Path(alias="novelId")]
ChapterNumPath = Annotated[int, Path(alias="chapterNum", ge=0)]


@router.get("/novels", response_model=list[PublicNovelSummary], operation_id="list_novels")
async def list_novels(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[PublicNovelSummary] | Response:
    stmt = select(ReaderNovel).order_by(ReaderNovel.title.asc(), ReaderNovel.novel_id.asc())
    novels = (await db.execute(stmt)).scalars().all()

    fingerprint = (
        "|".join(f"{n.novel_id}:{n.toc_version}:{n.updated_at.isoformat()}" for n in novels)
        if novels
        else "empty"
    )
    etag = make_etag(f"novels:{fingerprint}")
    if etag_matches(request.headers.get("if-none-match"), etag):
        return not_modified_response(etag, NOVELS_CACHE_CONTROL)

    apply_cache_headers(response, etag, NOVELS_CACHE_CONTROL)
    return [PublicNovelSummary.model_validate(novel) for novel in novels]


@router.get("/novels/{novelId}", response_model=PublicNovelSummary, operation_id="get_novel")
async def get_novel(
    novel_id: NovelIdPath,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> PublicNovelSummary | Response:
    novel = (
        await db.execute(select(ReaderNovel).where(ReaderNovel.novel_id == novel_id))
    ).scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")

    etag = make_etag(f"novel:{novel.novel_id}:{novel.toc_version}:{novel.updated_at.isoformat()}")
    if etag_matches(request.headers.get("if-none-match"), etag):
        return not_modified_response(etag, NOVELS_CACHE_CONTROL)

    apply_cache_headers(response, etag, NOVELS_CACHE_CONTROL)
    return PublicNovelSummary.model_validate(novel)


@router.get(
    "/novels/{novelId}/chapters",
    response_model=list[PublicChapterSummary],
    operation_id="list_novel_chapters",
)
async def list_novel_chapters(
    novel_id: NovelIdPath,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[PublicChapterSummary] | Response:
    novel = (
        await db.execute(select(ReaderNovel).where(ReaderNovel.novel_id == novel_id))
    ).scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")

    etag = make_etag(f"toc:{novel.novel_id}:{novel.toc_version}")
    if etag_matches(request.headers.get("if-none-match"), etag):
        return not_modified_response(etag, TOC_CACHE_CONTROL)

    chapter_stmt = (
        select(
            ReaderChapter.chapter_id,
            ReaderChapter.chapter_num,
            ReaderChapter.title,
            ReaderChapter.published_at,
            ReaderChapter.updated_at,
        )
        .where(ReaderChapter.novel_id == novel_id)
        .order_by(ReaderChapter.chapter_num.asc())
    )
    rows = (await db.execute(chapter_stmt)).all()

    apply_cache_headers(response, etag, TOC_CACHE_CONTROL)
    return [
        PublicChapterSummary(
            chapter_id=row.chapter_id,
            chapter_num=row.chapter_num,
            title=row.title,
            published_at=row.published_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.get(
    "/novels/{novelId}/chapters/{chapterNum}",
    response_model=PublicChapterDetail,
    operation_id="get_novel_chapter",
)
async def get_novel_chapter(
    novel_id: NovelIdPath,
    chapter_num: ChapterNumPath,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> PublicChapterDetail | Response:
    novel = (
        await db.execute(select(ReaderNovel).where(ReaderNovel.novel_id == novel_id))
    ).scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")

    chapter = (
        await db.execute(
            select(ReaderChapter).where(
                ReaderChapter.novel_id == novel_id,
                ReaderChapter.chapter_num == chapter_num,
            )
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    prev_row = (
        await db.execute(
            select(ReaderChapter.chapter_num, ReaderChapter.title)
            .where(
                ReaderChapter.novel_id == novel_id,
                ReaderChapter.chapter_num < chapter_num,
            )
            .order_by(ReaderChapter.chapter_num.desc())
            .limit(1)
        )
    ).first()
    next_row = (
        await db.execute(
            select(ReaderChapter.chapter_num, ReaderChapter.title)
            .where(
                ReaderChapter.novel_id == novel_id,
                ReaderChapter.chapter_num > chapter_num,
            )
            .order_by(ReaderChapter.chapter_num.asc())
            .limit(1)
        )
    ).first()

    prev_nav = PublicChapterNav(chapter_num=prev_row.chapter_num, title=prev_row.title) if prev_row else None
    next_nav = PublicChapterNav(chapter_num=next_row.chapter_num, title=next_row.title) if next_row else None

    prev_sig = f"{prev_nav.chapter_num}:{prev_nav.title}" if prev_nav else "none"
    next_sig = f"{next_nav.chapter_num}:{next_nav.title}" if next_nav else "none"
    etag = make_etag(
        f"chapter:{novel.novel_id}:{novel.title}:{chapter.chapter_id}:{chapter.chapter_num}:"
        f"{chapter.title}:{chapter.content_hash}:{chapter.external_version or ''}:{prev_sig}:{next_sig}"
    )
    if etag_matches(request.headers.get("if-none-match"), etag):
        return not_modified_response(etag, CHAPTER_CACHE_CONTROL)

    apply_cache_headers(response, etag, CHAPTER_CACHE_CONTROL)
    return PublicChapterDetail(
        novel_id=novel.novel_id,
        novel_title=novel.title,
        chapter_id=chapter.chapter_id,
        chapter_num=chapter.chapter_num,
        title=chapter.title,
        body=chapter.body,
        content_hash=chapter.content_hash,
        external_version=chapter.external_version,
        prev=prev_nav,
        next=next_nav,
    )


def _compute_client_hash(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",", 1)[0].strip()
    elif request.client is not None:
        client_ip = request.client.host
    else:
        client_ip = ""
    user_agent = request.headers.get("user-agent", "")
    raw = f"{reader_settings.feedback_hash_salt}|{client_ip}|{user_agent}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _build_feedback_payload(payload: FeedbackCreateRequest) -> dict[str, Any]:
    if isinstance(payload, FeedbackReactionCreateRequest):
        return {"emoji": payload.emoji}
    if isinstance(payload, FeedbackIssueCreateRequest):
        result: dict[str, Any] = {
            "category": payload.category,
            "message": payload.message,
        }
        if payload.anchor is not None:
            result["anchor"] = payload.anchor.model_dump(by_alias=True)
        return result
    assert isinstance(payload, FeedbackCommentCreateRequest)
    result = {"message": payload.message}
    if payload.anchor is not None:
        result["anchor"] = payload.anchor.model_dump(by_alias=True)
    return result


@router.post(
    "/novels/{novelId}/chapters/{chapterNum}/feedback",
    response_model=FeedbackCreateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_chapter_feedback",
)
async def create_chapter_feedback(
    novel_id: NovelIdPath,
    chapter_num: ChapterNumPath,
    payload: FeedbackCreateRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> FeedbackCreateResponse:
    response.headers["Cache-Control"] = "no-store"

    chapter = (
        await db.execute(
            select(ReaderChapter).where(
                ReaderChapter.novel_id == novel_id,
                ReaderChapter.chapter_num == chapter_num,
            )
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    requested_hash = (payload.content_hash or "").strip()
    content_hash = requested_hash or chapter.content_hash

    feedback = ReaderFeedback(
        novel_id=chapter.novel_id,
        chapter_id=chapter.chapter_id,
        chapter_num=chapter.chapter_num,
        content_hash=content_hash,
        external_version=chapter.external_version,
        kind=payload.kind,
        payload=_build_feedback_payload(payload),
        client_hash=_compute_client_hash(request),
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return FeedbackCreateResponse(
        feedback_id=feedback.feedback_id,
        created_at=feedback.created_at,
    )
