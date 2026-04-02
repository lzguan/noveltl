"""
Router functions for novels service.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user, get_optional_user
from ..auth.models import User
from ..database import get_db
from ..exceptions import DataTooLongException, InsufficientPermissionsException
from ..languages.exceptions import LanguageNotFoundException
from ..schemas import OperationStatus
from . import schemas
from .exceptions import (
    ChapterNotFoundException,
    ChapterNumDuplicateException,
    DeleteRevisionFailedException,
    DuplicateNovelAssociationException,
    NovelAssociationNotFoundException,
    NovelNotFoundException,
    RevisionMakePrimaryFailedException,
    RevisionNotFoundException,
    RevisionNotPublicException,
    RevisionTextNotFoundException,
    RevisionTextOutdatedException,
)
from .service import (
    insert_chapter,
    insert_novel,
    insert_novel_association,
    insert_revision,
    make_primary_revision,
    make_public_revision,
    modify_novel,
    modify_revision,
    modify_revision_text,
    query_chapter_by_id,
    query_chapters_by_novel,
    query_novel_associations,
    query_novel_by_id,
    query_novels_by_current_user,
    query_novels_by_title,
    query_revision_by_id,
    query_revision_text_by_id,
    query_revision_text_by_most_recent,
    query_revision_text_ids_by_revision_id,
    query_revision_text_status,
    query_revisions_by_chapter,
    query_revisions_by_novel,
    remove_novel_association,
    remove_revision,
)

router = APIRouter()


@router.get("/novels", response_model=list[schemas.Novel])
async def read_novels(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    title_contains: str | None = Query(default=None, alias="title-contains"),
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
    title_contains: str | None = Query(default=None, alias="title-contains"),
):
    """
    Endpoint for retrieving novels that the user has special access to.
    """
    novels = query_novels_by_current_user(db, current_user, editable, title_contains)
    return novels


@router.get("/novels/{novel_id}", response_model=schemas.Novel)
async def read_novel(
    novel_id: uuid.UUID,
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


@router.get("/chapters", response_model=list[schemas.Chapter])
async def read_chapters_by_novel(
    novel_id: Annotated[uuid.UUID, Query(alias="novel-id")],
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


@router.get("/chapters/{chapter_id}", response_model=schemas.Chapter)
async def read_chapter_by_id(
    chapter_id: uuid.UUID,
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


@router.get("/revisions/{revision_id}", response_model=schemas.Revision)
async def read_revision(
    revision_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Endpoint for retrieving chapter revision by id.

    Raises:
        404: Revision not found (or insufficient permissions).
    """
    try:
        revision = query_revision_by_id(db, current_user, revision_id)
    except RevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Revision with id {revision_id} not found."
        ) from e
    return revision


@router.get("/novels/{novel_id}/revisions", response_model=list[schemas.Revision])
async def read_revisions_by_novel(
    novel_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    start: int | None = None,
    end: int | None = None,
    is_public: Annotated[bool | None, Query(alias="is-public")] = None,
    is_primary: Annotated[bool | None, Query(alias="is-primary")] = None,
):
    """
    Endpoint for retrieving revisions in bulk by novel.

    Raises:
        404: Novel not found (or insufficient permissions).
    """
    try:
        revisions = query_revisions_by_novel(db, current_user, novel_id, start, end, is_public, is_primary)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {novel_id} not found.") from e
    return revisions


@router.get("/chapters/{chapter_id}/revisions", response_model=list[schemas.Revision])
async def read_revisions_by_chapter(
    chapter_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    is_public: Annotated[bool | None, Query(alias="is-public")] = None,
    is_primary: Annotated[bool | None, Query(alias="is-primary")] = None,
):
    """
    Endpoint for retrieving chapter revisions from a chapter.

    Raises:
        404: Chapter not found (or insufficient permissions).
    """
    try:
        revisions = query_revisions_by_chapter(db, current_user, chapter_id, is_public, is_primary)
    except ChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Chapter with id {chapter_id} not found."
        ) from e
    return revisions


@router.get("/revisions/{revision_id}/text", response_model=schemas.RevisionText)
async def read_revision_text(
    revision_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Endpoint for retrieving the most recent text of a revision.

    Raises:
        404: Revision not found, or revision has no text.
    """
    try:
        revision_text = query_revision_text_by_most_recent(db, current_user, revision_id)
    except RevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Revision with id {revision_id} not found."
        ) from e
    except RevisionTextNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Text for revision {revision_id} not found."
        ) from e
    return revision_text


@router.get("/revision-texts/{revision_text_id}", response_model=schemas.RevisionText)
async def read_revision_text_by_id(
    revision_text_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Endpoint for retrieving a specific version of revision text by its id.

    Raises:
        404: Revision text not found (or insufficient permissions).
    """
    try:
        revision_text = query_revision_text_by_id(db, current_user, revision_text_id)
    except RevisionTextNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Revision text with id {revision_text_id} not found."
        ) from e
    return revision_text


@router.get("/revisions/{revision_id}/text-versions", response_model=list[schemas.RevisionTextMeta])
async def read_revision_text_versions(
    revision_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Endpoint for retrieving all text version metadata for a revision.
    Returns an empty list if the revision has no text versions or doesn't exist.
    """
    versions = query_revision_text_ids_by_revision_id(db, current_user, revision_id)
    return versions


@router.get("/revisions/{revision_id}/text-status/{revision_text_id}", response_model=OperationStatus)
async def read_revision_text_status(
    revision_id: uuid.UUID,
    revision_text_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Check whether a revision_text_id is the latest version for a revision.

    Raises:
        404: Revision text not found (or insufficient read permissions).
        409: Revision text is outdated.
    """
    try:
        result = query_revision_text_status(db, current_user, revision_id, revision_text_id)
    except RevisionTextNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision text not found.") from e
    except RevisionTextOutdatedException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Revision text is outdated. Please refresh and try again."
        ) from e
    return result


@router.post("/novels", response_model=schemas.Novel)
async def create_novel(
    request: schemas.CreateNovel,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Add a new novel to the database.

    Raises:
        404: Language code not found.
        400: Data in some field is too long.
    """
    try:
        db_novel = insert_novel(db, current_user, request)
    except LanguageNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Language with language code {request.language_code} not found.",
        ) from e
    except DataTooLongException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data in some field is too long.") from e
    return db_novel


@router.patch("/novels/{novel_id}", response_model=schemas.Novel)
async def update_novel(
    novel_id: uuid.UUID,
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


@router.post("/novels/{novel_id}/chapters", response_model=schemas.Chapter)
async def create_chapter(
    novel_id: uuid.UUID,
    request: schemas.CreateChapter,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Insert a new chapter into the database.

    Raises:
        404: Novel not found.
        409: Chapter with this chapter number already exists in this novel.
        401: Insufficient permissions.
    """
    try:
        db_chapter = insert_chapter(db, current_user, novel_id, request)
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
    return db_chapter


@router.post("/chapters/{chapter_id}/revisions", response_model=schemas.RevisionData)
async def create_revision(
    chapter_id: uuid.UUID,
    request: schemas.CreateRevision,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Insert a new chapter revision into database. Returns revision metadata and initial empty text.

    Raises:
        404: Chapter not found.
        401: Insufficient permissions.
        400: Field in request too long.
    """
    try:
        new_revision, new_revision_text = insert_revision(db, current_user, chapter_id, request)
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
    return schemas.RevisionData(
        metadata=schemas.Revision.model_validate(new_revision, from_attributes=True),
        content=schemas.RevisionText.model_validate(new_revision_text, from_attributes=True),
    )


@router.patch("/revisions/{revision_id}", response_model=schemas.Revision)
async def update_revision(
    revision_id: uuid.UUID,
    request: schemas.UpdateRevision,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update a revision's metadata.

    Raises:
        404: Revision not found.
        401: Insufficient permissions.
        400: Field in request too long.
    """
    try:
        db_revision = modify_revision(db, current_user, revision_id, request)
    except RevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Revision with id {revision_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to perform this action."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Field in request too long.") from e
    return db_revision


@router.post("/revisions/{revision_id}/publish", response_model=schemas.Revision)
async def publish_revision(
    revision_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Publish revision with revision_id.

    Raises:
        404: Revision not found.
        401: Insufficient permissions.
    """
    try:
        db_revision = make_public_revision(db, current_user, revision_id)
    except RevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Revision with id {revision_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to perform this action."
        ) from e
    return db_revision


@router.post("/revisions/{revision_id}/make-primary", response_model=schemas.Revision)
async def set_primary_revision(
    revision_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Mark revision with revision_id as primary.

    Raises:
        404: Revision not found.
        403: Revision is not public yet.
        409: Race condition setting primary revision.
        401: Insufficient permissions.
    """
    try:
        db_revision = make_primary_revision(db, current_user, revision_id)
    except RevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Revision with id {revision_id} not found."
        ) from e
    except RevisionNotPublicException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Revision must be public before it can be set as primary."
        ) from e
    except RevisionMakePrimaryFailedException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Failed to set primary revision. Probably a race condition."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to perform this action."
        ) from e
    return db_revision


@router.patch("/revisions/{revision_id}/text", response_model=OperationStatus)
async def update_revision_text(
    revision_id: uuid.UUID,
    request: schemas.UpdateRevisionText,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Apply text operations to the most recent text of a revision. Uses optimistic concurrency
    via revision_text_id — if the text has been modified since the client last fetched it,
    a 409 is returned.

    Raises:
        404: Revision text not found.
        409: Revision text is outdated (someone else modified it).
        401: Insufficient permissions to modify this revision.
    """
    try:
        result = modify_revision_text(db, current_user, revision_id, request.revision_text_id, request.text_ops)
    except RevisionTextNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Revision text not found for revision {revision_id}."
        ) from e
    except RevisionTextOutdatedException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Revision text is outdated. Please refresh and try again."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to modify this revision."
        ) from e
    return result


@router.delete("/revisions/{revision_id}", response_model=OperationStatus)
async def delete_revision(
    revision_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete a revision from the database.

    Raises:
        404: Revision not found.
        401: Insufficient permissions.
        500: Delete failed for other reasons.
    """
    try:
        delete_status = remove_revision(db, current_user, revision_id)
    except RevisionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Revision with id {revision_id} not found."
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to perform this action."
        ) from e
    except DeleteRevisionFailedException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete revision."
        ) from e
    return delete_status


# --- Novel Associations ---


@router.get("/novel-associations", response_model=list[schemas.NovelAssociation])
async def read_novel_associations(
    source_novel_id: Annotated[uuid.UUID, Query(alias="source-novel-id")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    List all associations for a given source novel.

    Raises:
        404: Source novel not found or insufficient permissions.
    """
    try:
        associations = query_novel_associations(db, current_user, source_novel_id)
    except NovelNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Novel with id {source_novel_id} not found."
        ) from e
    return associations


@router.post("/novel-associations", response_model=schemas.NovelAssociation, status_code=status.HTTP_201_CREATED)
async def create_novel_association(
    request: schemas.CreateNovelAssociation,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a novel-to-novel association. Requires owner or editor role on the source novel.

    Raises:
        404: Source or target novel not found.
        409: Association with same (source, target, type) already exists.
        401: Insufficient permissions on the source novel.
    """
    try:
        association = insert_novel_association(db, current_user, request)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source or target novel not found.") from e
    except DuplicateNovelAssociationException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An association of this type between these novels already exists.",
        ) from e
    except InsufficientPermissionsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Insufficient permissions to perform this action."
        ) from e
    return association


@router.delete("/novel-associations/{association_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_novel_association(
    association_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete a novel association. Requires owner or editor role on the source novel.

    Raises:
        404: Association not found or insufficient permissions.
    """
    try:
        remove_novel_association(db, current_user, association_id)
    except NovelAssociationNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Novel association with id {association_id} not found.",
        ) from e
