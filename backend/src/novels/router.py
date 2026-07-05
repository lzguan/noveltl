"""
Router functions for novels service.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from src.novels.service import query_novel_and_users_by_id

from ..auth.dependencies import get_current_user, get_optional_user
from ..auth.models import User
from ..database import get_db
from ..exceptions import DataTooLongException, InsufficientPermissionsException
from ..languages.exceptions import LanguageNotFoundException
from ..requests.cache import redis_cache
from ..requests.decorators import attl_cache, serialize_response_model
from ..schemas import DetailHTTPErrorResponse, OperationStatus, RequestConflictErrorResponse
from . import schemas
from .exceptions import (
    ChapterContentNotFoundException,
    ChapterContentOutdatedException,
    ChapterDeleteFailedException,
    ChapterNotFoundException,
    ChapterNumDuplicateException,
    NovelNotFoundException,
    SourceWorkNotFoundException,
)
from .service import (
    insert_chapter,
    insert_novel,
    insert_source_work,
    make_public_chapter,
    modify_chapter,
    modify_chapter_content,
    modify_novel,
    modify_source_work,
    query_chapter_by_id,
    query_chapter_content_by_id,
    query_chapter_content_by_most_recent,
    query_chapter_content_ids_by_chapter_id,
    query_chapter_content_status,
    query_chapters_by_novel,
    query_novel_by_id,
    query_novels_by_current_user,
    query_novels_by_source_work,
    query_novels_by_title,
    query_source_work_by_id,
    query_source_works_by_title,
    remove_chapter,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Source Work endpoints
# ---------------------------------------------------------------------------


@router.get("/source-works", response_model=list[schemas.SourceWorkData])
async def read_source_works(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    title_contains: Annotated[str | None, Query(alias="titleContains")] = None,
    ret_novels: Annotated[bool, Query(alias="retNovels")] = False,
):
    """
    Endpoint for retrieving source works in bulk, optionally filtered by title substring.
    """
    source_works = query_source_works_by_title(db, current_user, title_contains, ret_novels)
    return [schemas.SourceWorkData(source_work=sw, novels=novels) for sw, novels in source_works]


@router.get("/source-works/{sourceWorkId}", response_model=schemas.SourceWork)
async def read_source_work(
    source_work_id: Annotated[uuid.UUID, Path(alias="sourceWorkId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Endpoint for retrieving a source work by id.

    Raises:
        404: Source work not found (or insufficient permissions).
    """
    try:
        source_work = query_source_work_by_id(db, current_user, source_work_id)
    except SourceWorkNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Source work with id {source_work_id} not found."
        ) from e
    return source_work


@router.get("/source-works/{sourceWorkId}/novels", response_model=list[schemas.Novel])
async def read_novels_by_source_work(
    source_work_id: Annotated[uuid.UUID, Path(alias="sourceWorkId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Endpoint for retrieving novels belonging to a source work.

    Raises:
        404: Source work not found (or insufficient permissions).
    """
    try:
        novels = query_novels_by_source_work(db, current_user, source_work_id)
    except SourceWorkNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Source work with id {source_work_id} not found."
        ) from e
    return novels


@router.post("/source-works", response_model=schemas.SourceWork)
async def create_source_work(
    request: schemas.CreateSourceWork,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a new source work.

    Raises:
        400: Data in some field is too long.
    """
    try:
        source_work = insert_source_work(db, current_user, request)
    except DataTooLongException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data in some field is too long.") from e
    return source_work


@router.patch("/source-works/{sourceWorkId}", response_model=schemas.SourceWork)
async def update_source_work(
    source_work_id: Annotated[uuid.UUID, Path(alias="sourceWorkId")],
    request: schemas.UpdateSourceWork,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update a source work's metadata.

    Raises:
        404: Source work not found.
        401: Insufficient permissions.
        400: Data in some field exceeds maximum length.
    """
    try:
        source_work = modify_source_work(db, current_user, source_work_id, request)
    except SourceWorkNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source work not found.") from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to update this source work."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Data in some field exceeds the maximum possible length."
        ) from e
    return source_work


# ---------------------------------------------------------------------------
# Novel endpoints
# ---------------------------------------------------------------------------


@router.get("/novels", response_model=list[schemas.Novel])
async def read_novels(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    title_contains: Annotated[str | None, Query(alias="titleContains")] = None,
):
    """
    Endpoint for retrieving novels in bulk.
    """
    novels = query_novels_by_title(db, current_user, title_contains)
    return novels


@router.get("/novels/mine", response_model=list[schemas.Novel])
async def read_novels_mine(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    editable: bool = False,
    title_contains: str | None = Query(default=None, alias="titleContains"),
):
    """
    Endpoint for retrieving novels that the user has special access to.
    """
    novels = query_novels_by_current_user(db, current_user, editable, title_contains)
    return novels


@router.get("/novels/{novelId}", response_model=schemas.Novel)
async def read_novel(
    novel_id: Annotated[uuid.UUID, Path(alias="novelId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Endpoint for retrieving a novel by id.

    Raises:
        404: Novel not found (or insufficient permissions).
    """
    try:
        novel = query_novel_by_id(db, current_user, novel_id)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found.") from e
    return novel


@router.get("/novels/{novelId}/with-contributors", response_model=schemas.NovelAndUsers)
async def read_novel_with_contributors(
    novel_id: Annotated[uuid.UUID, Path(alias="novelId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Endpoint for retrieving a novel and its associated users.

    Raises:
        404: Novel not found (or insufficient permissions).
    """
    try:
        novel_and_users = query_novel_and_users_by_id(db, current_user, novel_id)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found.") from e
    return novel_and_users


@router.post("/novels", response_model=schemas.Novel)
async def create_novel(
    request: schemas.CreateNovel,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Add a new novel to the database.

    Raises:
        404: Language code or source work not found.
        400: Data in some field is too long.
    """
    try:
        db_novel = insert_novel(db, current_user, request)
    except SourceWorkNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Source work with id {request.source_work_id} not found."
        ) from e
    except LanguageNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Language with language code {request.language_code} not found.",
        ) from e
    except DataTooLongException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data in some field is too long.") from e
    return db_novel


@router.patch("/novels/{novelId}", response_model=schemas.Novel)
async def update_novel(
    novel_id: Annotated[uuid.UUID, Path(alias="novelId")],
    request: schemas.UpdateNovel,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update the novel with novel_id.

    Raises:
        404: Novel not found.
        401: Insufficient permissions (user is not owner/editor).
        400: Data in some field exceeds maximum length.
    """
    try:
        db_novel = modify_novel(db, current_user, novel_id, request)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found.") from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to update this novel."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Data in some field exceeds the maximum possible length."
        ) from e
    return db_novel


# ---------------------------------------------------------------------------
# Chapter endpoints
# ---------------------------------------------------------------------------


@router.get("/chapters", response_model=list[schemas.Chapter])
async def read_chapters_by_novel(
    novel_id: Annotated[uuid.UUID, Query(alias="novelId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    start: int | None = None,
    end: int | None = None,
):
    """
    Endpoint for retrieving chapters by novel_id.

    Raises:
        404: Novel not found (or insufficient permissions).
    """
    try:
        chapters = query_chapters_by_novel(db, current_user, novel_id, start, end)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found.") from e
    return chapters


@router.get("/chapters/{chapterId}", response_model=schemas.Chapter)
async def read_chapter_by_id(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Endpoint for retrieving chapter by id.

    Raises:
        404: Chapter not found (or insufficient permissions).
    """
    try:
        chapter = query_chapter_by_id(db, current_user, chapter_id)
    except ChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter with id {chapter_id} not found."
        ) from e
    return chapter


@router.post("/novels/{novelId}/chapters", response_model=schemas.ChapterData)
async def create_chapter(
    novel_id: Annotated[uuid.UUID, Path(alias="novelId")],
    request: schemas.CreateChapter,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Insert a new chapter into the database. Returns chapter metadata and initial empty content.

    Raises:
        404: Novel not found.
        409: Chapter with this chapter number already exists in this novel.
        401: Insufficient permissions.
    """
    try:
        chapter, chapter_content = insert_chapter(db, current_user, novel_id, request)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found.") from e
    except ChapterNumDuplicateException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chapter with this chapter number already exists in this novel.",
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to perform this action."
        ) from e
    return schemas.ChapterData(
        metadata=schemas.Chapter.model_validate(chapter, from_attributes=True),
        content=schemas.ChapterContent.model_validate(chapter_content, from_attributes=True),
    )


@router.patch("/chapters/{chapterId}", response_model=schemas.Chapter)
async def update_chapter(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    request: schemas.UpdateChapter,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update chapter metadata.

    Raises:
        404: Chapter not found.
        401: Insufficient permissions.
        400: Field in request too long.
    """
    try:
        chapter = modify_chapter(db, current_user, chapter_id, request)
    except ChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter with id {chapter_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to perform this action."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Field in request too long.") from e
    return chapter


@router.delete("/chapters/{chapterId}", response_model=OperationStatus)
async def delete_chapter(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete a chapter from the database.

    Raises:
        404: Chapter not found.
        401: Insufficient permissions.
        500: Delete failed for other reasons.
    """
    try:
        delete_status = remove_chapter(db, current_user, chapter_id)
    except ChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter with id {chapter_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to perform this action."
        ) from e
    except ChapterDeleteFailedException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete chapter."
        ) from e
    return delete_status


@router.post("/chapters/{chapterId}/publish", response_model=schemas.Chapter)
async def action_publish_chapter(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Publish a chapter (make it public).

    Raises:
        404: Chapter not found.
        401: Insufficient permissions.
    """
    try:
        chapter = make_public_chapter(db, current_user, chapter_id)
    except ChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter with id {chapter_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to perform this action."
        ) from e
    return chapter


# ---------------------------------------------------------------------------
# Chapter Content endpoints
# ---------------------------------------------------------------------------


@router.get("/chapters/{chapterId}/content", response_model=schemas.ChapterContent)
async def read_chapter_content(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Endpoint for retrieving the most recent content of a chapter.

    Raises:
        404: Chapter not found, or chapter has no content.
    """
    try:
        content = query_chapter_content_by_most_recent(db, current_user, chapter_id)
    except ChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter with id {chapter_id} not found."
        ) from e
    except ChapterContentNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Content for chapter {chapter_id} not found."
        ) from e
    return content


@router.get("/chapter-contents/{chapterContentId}", response_model=schemas.ChapterContent)
async def read_chapter_content_by_id(
    chapter_content_id: Annotated[uuid.UUID, Path(alias="chapterContentId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Endpoint for retrieving a specific version of chapter content by its id.

    Raises:
        404: Chapter content not found (or insufficient permissions).
    """
    try:
        content = query_chapter_content_by_id(db, current_user, chapter_content_id)
    except ChapterContentNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter content with id {chapter_content_id} not found."
        ) from e
    return content


@router.get("/chapters/{chapterId}/content-versions", response_model=list[schemas.ChapterContentMeta])
async def read_chapter_content_versions(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Endpoint for retrieving all content version metadata for a chapter.
    Returns an empty list if the chapter has no content versions or doesn't exist.
    """
    versions = query_chapter_content_ids_by_chapter_id(db, current_user, chapter_id)
    return versions


@router.get("/chapters/{chapterId}/content-status/{chapterContentId}", response_model=OperationStatus)
async def read_chapter_content_status(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    chapter_content_id: Annotated[uuid.UUID, Path(alias="chapterContentId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Check whether a chapter_content_id is the latest version for a chapter.

    Raises:
        404: Chapter content not found (or insufficient read permissions).
        409: Chapter content is outdated.
    """
    try:
        result = query_chapter_content_status(db, current_user, chapter_id, chapter_content_id)
    except ChapterContentNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter content not found.") from e
    except ChapterContentOutdatedException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Chapter content is outdated. Please refresh and try again."
        ) from e
    return result


@router.patch(
    "/chapters/{chapterId}/content",
    response_model=schemas.ModifyChapterContentResponse,
    responses={
        401: {"model": DetailHTTPErrorResponse, "description": "Insufficient permissions to modify this chapter."},
        404: {"model": DetailHTTPErrorResponse, "description": "Chapter content not found."},
        409: {
            "model": RequestConflictErrorResponse,
            "description": "Chapter content is outdated, or the request key already exists.",
        },
    },
)
@attl_cache(
    ttl=60,
    cache=redis_cache,
    success_code=200,
    serialize_ret=serialize_response_model(schemas.ModifyChapterContentResponse),
)
async def update_chapter_content(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    request: schemas.UpdateChapterContent,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request_key: Annotated[uuid.UUID | None, Query(alias="requestKey")] = None,
):
    """
    Apply text operations to the most recent content of a chapter. Uses optimistic concurrency
    via chapter_content_id -- if the content has been modified since the client last fetched it,
    a 409 is returned.

    Raises:
        404: Chapter content not found.
        409: Chapter content is outdated (someone else modified it).
        401: Insufficient permissions to modify this chapter.
    """
    try:
        result = modify_chapter_content(db, current_user, chapter_id, request.chapter_content_id, request.text_ops)
    except ChapterContentNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter content not found for chapter {chapter_id}."
        ) from e
    except ChapterContentOutdatedException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Chapter content is outdated. Please refresh and try again."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to modify this chapter."
        ) from e
    return result
