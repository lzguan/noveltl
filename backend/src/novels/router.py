"""
Router functions for novels service.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user, get_optional_user
from ..auth.models import User
from ..database import get_db
from ..exceptions import DataTooLongException, InsufficientPermissionsException
from ..languages.exceptions import LanguageNotFoundException
from . import schemas
from .exceptions import (
    ChapterNumDuplicateException,
    NovelNotFoundException,
    RawChapterNotFoundException,
    RawChapterRevisionMakePrimaryFailedException,
    RawChapterRevisionNotFoundException,
    RawChapterRevisionNotPublicException,
)
from .service import (
    insert_novel,
    insert_raw_chapter,
    insert_raw_chapter_revision,
    make_final_raw_chapter_revision,
    make_primary_raw_chapter_revision,
    modify_novel,
    modify_raw_chapter_revision,
    publish_raw_chapter_revision,
    query_novel_by_id,
    query_novels_by_current_user,
    query_novels_by_title,
    query_raw_chapter_by_id,
    query_raw_chapter_revision_by_id,
    query_raw_chapter_revisions_by_novel,
    query_raw_chapter_revisions_by_raw_chapter,
    query_raw_chapters_by_novel,
    remove_raw_chapter_revision,
)

router = APIRouter()

@router.get(
    '/novels',
    response_model=list[schemas.Novel]
)
async def read_novels(
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User | None, Depends(get_optional_user)],
    title_contains : str | None = None
    ):
    """
    Endpoint for retrieving novels in bulk.

    Args:
        db: Database dependency.
        current_user: Optional current user dependency.
        title_contains: string to filter novel titles by.
    """
    novels = query_novels_by_title(db, current_user, title_contains)
    return novels

@router.get(
    '/novels/mine',
    response_model=list[schemas.Novel]
)
async def read_novels_mine(
        db: Annotated[Session, Depends(get_db)],
        current_user : Annotated[User , Depends(get_current_user)],
        editable : bool = False,
        title_contains : str | None = Query(default=None, alias="titleContains")
    ):
    """
    Endpoint for retrieving novels that the user has special access to.

    Args:
        db: Database dependency.
        current_user: Current user dependency.
        editable: If True, return only novels which the user can edit (i.e. has owner or editor permissions).
    """
    novels = query_novels_by_current_user(db, current_user, editable, title_contains)
    return novels

@router.get(
    '/novels/{novel_id}',
    response_model=schemas.Novel
)
async def read_novel(
    novel_id : int,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User | None, Depends(get_optional_user)]
    ):
    """
    Endpoint for retrieving a novel from database.

    Args:
        novel_id: id of novel to query
        current_user: Optional current user dependency.
        db: Database dependency
    """
    try:
        novel = query_novel_by_id(db, current_user, novel_id)
    except NovelNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Novel with {novel_id} not found."
        ) from e
    return novel

@router.get(
    '/chapters',
    response_model=list[schemas.RawChapter]
)
async def read_chapters_by_novel(
    novel_id : int,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User | None, Depends(get_optional_user)],
    start : int | None = None,
    end : int | None = None
    ):
    """
    Endpoint for retrieving raw chapters by novel_id.

    Args:
        novel_id: id of novel to query from.
        db: Database dependency.
        current_user: Optional current user dependency.
        start: Optional query parameter. Will filter by chapters with chapter_num >= start.
        end: Optional query parameter. Will filter by chapters with chapter_num < end.
    """
    try:
        chapters = query_raw_chapters_by_novel(db, current_user, novel_id, start, end)
    except NovelNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel not found."
        ) from e
    return chapters

@router.get(
    '/chapters/{chapter_id}',
    response_model=schemas.RawChapter
)
async def read_chapter_by_id(
    chapter_id : int,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User | None, Depends(get_optional_user)]
):
    """
    Endpoint for retrieving raw chapter by id.

    Args:
        chapter_id: id of chapter to query.
        db: Database dependency.
        current_user: Optional current user dependency.
    """
    try:
        chapter = query_raw_chapter_by_id(db, current_user, chapter_id)
    except RawChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter with id {chapter_id} not found."
        ) from e
    return chapter

@router.get(
    '/revisions/{chapter_revision_id}',
    response_model=schemas.RawChapterRevision
)
async def read_chapter_revision(chapter_revision_id : int, db : Annotated[Session, Depends(get_db)], current_user : Annotated[User | None, Depends(get_optional_user)]):
    try:
        revision = query_raw_chapter_revision_by_id(db, current_user, chapter_revision_id)
    except RawChapterRevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {chapter_revision_id} not found."
        ) from e
    return revision

@router.get(
    '/novels/{novel_id}/revisions',
    response_model=list[schemas.RawChapterRevisionMeta]
)
async def read_chapter_revisions_by_novel(
    novel_id : int,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User | None, Depends(get_optional_user)],
    start : int | None = None,
    end : int | None = None,
    is_public : bool | None = None,
    is_primary : bool | None = None,
    is_final : bool | None = None
    ):
    """
    Endpoint for retrieving chapter revisions in bulk.

    Args:
        novel_id: id of novel to retrieve chapters from.
        db: Database dependency.
        current_user: Optional current user dependency.
        start: Optional query parameter. Will filter by chapters with chapter_num >= start.
        end: Optional query parameter. Will filter by chapters with chapter_num < end.
        is_public: Filter only public novels.
        is_primary: Filter only primary novels.
    """
    try:
        revisions = query_raw_chapter_revisions_by_novel(db, current_user, novel_id, start, end, is_public, is_primary, is_final)
    except NovelNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Novel with id {novel_id} not found."
        ) from e
    return revisions

@router.get(
    '/chapters/{chapter_id}/revisions',
    response_model=list[schemas.RawChapterRevisionMeta]
)
async def read_chapter_revision_by_chapter(
    chapter_id : int,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User | None, Depends(get_optional_user)],
    is_public : bool | None = None,
    is_primary : bool | None = None
):
    """
    Endpoint for retrieving chapter revisions in bulk from a raw chapter.

    Args:
        raw_chapter_id: id of novel to retrieve chapters from.
        db: Database dependency.
        current_user: Optional current user dependency.
        is_public: Filter only public novels.
        is_primary: Filter only primary novels.
    """
    try:
        revisions = query_raw_chapter_revisions_by_raw_chapter(db, current_user, chapter_id, is_public, is_primary)
    except RawChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter with id {chapter_id} not found."
        ) from e
    return revisions

@router.post(
    '/novels',
    response_model=schemas.Novel
)
async def create_novel(
    request : schemas.CreateNovel,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Add a new novel to the database.

    Args:
        request: Metadata for new novel.
        db: Database dependency.
        current_user: Current user dependency.
    """
    try:
        db_novel = insert_novel(db, current_user, request)
    except LanguageNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Language with language code {request.language_code} not found."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data in some field is too long."
        ) from e

    return db_novel

@router.patch(
    '/novels/{novel_id}',
    response_model=schemas.Novel
)
async def update_novel(
    novel_id : int,
    request : schemas.UpdateNovel,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Update the novel with novel_id.

    Args:
        novel_id: id of novel to update.
        request: Updated metadata for novel. Fields that are None in request are not updated.
        db: Database dependency.
        current_user: Current user dependency.
    """
    try:
        db_novel = modify_novel(db, current_user, novel_id, request)
    except NovelNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data in some field exceeds the maximum possible length."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to update this resource."
        ) from e
    return db_novel

@router.post(
    '/novels/{novel_id}/chapters',
    response_model=schemas.RawChapter
)
async def create_chapter(
    novel_id : int,
    request : schemas.CreateRawChapter,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Insert a new raw chapter into the database.

    Args:
        novel_id: id of novel this chapter belongs to.
        request: Metadata for new raw chapter.
        db: Database dependency.
        current_user: Current user dependency.
    """
    try:
        db_raw_chapter = insert_raw_chapter(db, current_user, novel_id, request)
    except NovelNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Novel with id {novel_id} not found."
        ) from e
    except ChapterNumDuplicateException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chapter in this novel with corresponding chapter number already created."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        ) from e
    return db_raw_chapter

@router.post(
    '/chapters/{chapter_id}/revisions',
    response_model=schemas.RawChapterRevision
)
async def create_chapter_revision(
    chapter_id : int,
    request : schemas.CreateRawChapterRevision,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Insert a new raw chapter revision into database.

    Args:
        chapter_id: id of chapter this revision corresponds to.
        request: Data about revision.
        db: Database dependency.
        current_user: Current user dependency.
    """
    try:
        db_revision = insert_raw_chapter_revision(db, current_user, chapter_id, request)
    except RawChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter with id {chapter_id} not found."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field in request too long."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        ) from e
    return db_revision

@router.patch(
    '/revisions/{revision_id}',
    response_model=schemas.RawChapterRevision
)
async def update_chapter_revision(
    revision_id : int,
    request : schemas.UpdateRawChapterRevision,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Update a raw chapter revision in the database.

    Args:
        revision_id: id of revision to update.
        request: Updated data for this revision.
        db: Database dependency.
        current_user: Current_user dependency.
    """
    try:
        db_revision = modify_raw_chapter_revision(db, current_user, revision_id, request)
    except RawChapterRevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field in request too long."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        ) from e
    return db_revision

@router.patch(
    '/publish/revisions/{revision_id}',
    response_model=schemas.RawChapterRevision
)
async def update_publish_chapter_revision(
    revision_id : int,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Publish chapter revision with revision_id.

    Args:
        revision_id: id of revision to publish.
        db: Database dependency.
        current_user: Current user dependency.
    """
    try:
        db_revision = publish_raw_chapter_revision(db, current_user, revision_id)
    except RawChapterRevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        ) from e
    return db_revision

@router.patch(
    '/make-primary/revisions/{revision_id}',
    response_model=schemas.RawChapterRevision
)
async def update_make_primary_chapter_revision(
    revision_id : int,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Mark chapter revision with revision_id as primary.

    Args:
        revision_id: id of revision to make primary.
        db: Database dependency.
        current_user: Current user dependency.
    """
    try:
        db_revision = make_primary_raw_chapter_revision(db, current_user, revision_id)
    except RawChapterRevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        ) from e
    except RawChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server did not find a chapter associated with this revision"
        ) from e
    except RawChapterRevisionMakePrimaryFailedException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Commit to database failed. Probably a race condition."
        ) from e
    except RawChapterRevisionNotPublicException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Revision not public yet."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        ) from e
    return db_revision

@router.patch(
    '/finalize/revisions/{revision_id}',
    response_model=schemas.RawChapterRevision
)
async def update_make_final_chapter_revision(
    revision_id : int,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Finalize chapter revision with revision_id.

    Args:
        revision_id: id of revision to finalize.
        db: Database dependency.
        current_user: Current user dependency.
    """
    try:
        db_revision = make_final_raw_chapter_revision(db, current_user, revision_id)
    except RawChapterRevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        ) from e
    return db_revision

@router.delete(
    '/revisions/{revision_id}',
    response_model=schemas.DeleteRawChapterRevisionStatus
)
async def delete_chapter_revision(
    revision_id : int,
    db : Annotated[Session, Depends(get_db)],
    current_user : Annotated[User, Depends(get_current_user)]
    ):
    try:
        delete_status = remove_raw_chapter_revision(db, current_user, revision_id)
    except RawChapterRevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        ) from e
    return delete_status
