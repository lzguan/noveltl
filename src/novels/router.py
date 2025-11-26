"""
Router functions for novels service.
"""

from ..database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from .dependencies import *
from ..auth.dependencies import get_current_user, get_optional_user
from .service import *
from .schemas import *
from typing import Annotated

router = APIRouter()

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
    except NovelNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Novel with {novel_id} not found."
        )
    except NovelTooManyFoundException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"More than one novel with {novel_id} found."
        )
    return novel

@router.get(
    '/novels', 
    response_model=List[schemas.Novel]
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
    '/chapters', 
    response_model=List[schemas.RawChapter]
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
    chapters = query_raw_chapters_by_novel(db, current_user, novel_id, start, end)
    return chapters

@router.get(
    '/chapter-revisions/{chapter_revision_id}',
    response_model=schemas.RawChapterRevision
)
async def read_chapter_revision(chapter_revision_id : int, db : Annotated[Session, Depends(get_db)], current_user : Annotated[User | None, Depends(get_optional_user)]):
    try:
        revision = query_raw_chapter_revision_by_id(db, current_user, chapter_revision_id)
    except RawChapterRevisionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with {chapter_revision_id} not found."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access this resource."
        )
    return revision

@router.get(
    '/chapters-revisions', 
    response_model=Dict[int, List[schemas.RawChapterRevisionMeta]]
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
        chapters = query_raw_chapter_revisions_by_novel(db, current_user, novel_id, start, end, is_public, is_primary, is_final)
    except NovelNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Novel with id {novel_id} not found."
        )
    return chapters

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
    except LanguageNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Language with language id {request.language_id} not found."
        )
    except DataTooLongException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data in some field is too long."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient user permissions to create this resource."
        )
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
    except NovelNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found."
        )
    except NovelTooManyFoundException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="More than one novel with this id found."
        )
    except DataTooLongException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data in some field exceeds the maximum possible length."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to update this resource."
        )
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
    except NovelNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Novel with id {novel_id} not found."
        )
    except ChapterNumDuplicateException:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chapter in this novel with corresponding chapter number already created."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        )
    return db_raw_chapter

@router.post(
    '/chapters/{chapter_id}/revision', 
    response_model=schemas.RawChapterRevision
)
async def create_chapter_revision(
    chapter_id : int, 
    request : CreateRawChapterRevision, 
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
    except RawChapterNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter with id {chapter_id} not found."
        )
    except DataTooLongException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field in request too long."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        )
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
    except RawChapterRevisionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        )
    except DataTooLongException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field in request to long."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        )
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
    except RawChapterRevisionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Insufficient permissions to perform this action."
        )
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
        revision_id: id of revision to make primary..
        db: Database dependency.
        current_user: Current user dependency.
    """
    try:
        db_revision = make_primary_raw_chapter_revision(db, current_user, revision_id)
    except RawChapterRevisionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        )
    except RawChapterNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server did not find a chapter associated with this revision"
        )
    except RawChapterRevisionMakePrimaryFailedException:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Commit to database failed. Probably a race condition."
        )
    except RawChapterRevisionNotPublicException:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Revision not public yet."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Insufficient permissions to perform this action."
        )
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
    except RawChapterRevisionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Insufficient permissions to perform this action."
        )
    return db_revision

@router.delete(
    '/revisions/{revision_id}', 
    response_model=schemas.DeleteRawChapterRevisionStatus
)
async def delete_chapter_revision(
    revision_id : int, 
    db : Annotated[Session, Depends(get_db)], 
    current_user : Annotated[User, Depends(get_current_user)],
    force_remove : bool = False
    ):
    try:
        delete_status = remove_raw_chapter_revision(db, current_user, revision_id, force_remove=force_remove)
    except RawChapterRevisionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter revision with id {revision_id} not found."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Insufficient permissions to perform this action."
        )
    return delete_status