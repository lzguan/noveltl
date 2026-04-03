import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user, get_optional_user
from ..auth.models import User
from ..database import get_db
from ..exceptions import DataTooLongException, NotFoundException, UnknownError
from ..novels.exceptions import NovelNotFoundException
from . import schemas
from .dependencies import get_translation_dispatcher
from .exceptions import (
    DuplicateGlossaryContributorException,
    DuplicateGlossaryEntryException,
    EnqueueFailedException,
    GlossaryContributorNotFoundException,
    GlossaryEntryNotFoundException,
    GlossaryNotFoundException,
    GlossaryTranslationJobNotFoundException,
    InvalidSearchModeException,
    QueueFullException,
)
from .service import (
    create_translation_job,
    import_from_labels,
    insert_glossary,
    insert_glossary_contributor,
    insert_glossary_entry,
    modify_glossary,
    modify_glossary_contributor,
    modify_glossary_entry,
    query_glossaries,
    query_glossary,
    query_glossary_contributors,
    query_glossary_entries,
    query_glossary_entry,
    query_translation_job,
    query_translation_jobs,
    remove_glossary,
    remove_glossary_contributor,
    remove_glossary_entry,
    search_term_occurrences,
)
from .utils import TranslationDispatcher

router = APIRouter()


# --- Glossary CRUD ---


@router.get("/glossaries", response_model=list[schemas.Glossary])
def read_glossaries(
    novel_id: Annotated[uuid.UUID, Query(alias="novel-id")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    List glossaries for a novel.
    """
    return query_glossaries(db, novel_id, current_user)


@router.get("/glossaries/{glossary_id}", response_model=schemas.Glossary)
def read_glossary(
    glossary_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Get a glossary by id.

    Raises:
        404: Glossary not found.
    """
    try:
        return query_glossary(db, glossary_id, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary with id {glossary_id} not found.",
        ) from e


@router.post("/glossaries", response_model=schemas.Glossary, status_code=status.HTTP_201_CREATED)
def create_glossary(
    request: schemas.CreateGlossary,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a new glossary. The creator is automatically added as owner.

    Raises:
        404: Novel not found.
        400: Field value too long.
    """
    try:
        return insert_glossary(db, request, current_user)
    except NovelNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel not found.",
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A field value is too long.",
        ) from e


@router.patch("/glossaries/{glossary_id}", response_model=schemas.Glossary)
def update_glossary(
    glossary_id: uuid.UUID,
    request: schemas.UpdateGlossary,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update a glossary's name or description.

    Raises:
        404: Glossary not found.
        400: Field value too long.
    """
    try:
        return modify_glossary(db, glossary_id, request, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary with id {glossary_id} not found.",
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A field value is too long.",
        ) from e


@router.delete("/glossaries/{glossary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_glossary(
    glossary_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete a glossary (owner only).

    Raises:
        404: Glossary not found.
    """
    try:
        remove_glossary(db, glossary_id, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary with id {glossary_id} not found.",
        ) from e


# --- Glossary Entry CRUD ---


@router.get("/glossary-entries", response_model=list[schemas.GlossaryEntry])
def read_glossary_entries(
    glossary_id: Annotated[uuid.UUID, Query(alias="glossary-id")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    List entries for a glossary.
    """
    return query_glossary_entries(db, glossary_id, current_user)


@router.get("/glossary-entries/{glossary_entry_id}", response_model=schemas.GlossaryEntry)
def read_glossary_entry(
    glossary_entry_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Get a glossary entry by id.

    Raises:
        404: Entry not found.
    """
    try:
        return query_glossary_entry(db, glossary_entry_id, current_user)
    except GlossaryEntryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary entry with id {glossary_entry_id} not found.",
        ) from e


@router.post("/glossary-entries", response_model=schemas.GlossaryEntry, status_code=status.HTTP_201_CREATED)
def create_glossary_entry(
    request: schemas.CreateGlossaryEntry,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a new glossary entry.

    Raises:
        404: Glossary not found.
        409: Entry with same source_term + entity_type already exists.
        400: Field value too long.
    """
    try:
        return insert_glossary_entry(db, request, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Glossary not found.",
        ) from e
    except DuplicateGlossaryEntryException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An entry with this source term and entity type already exists in the glossary.",
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A field value is too long.",
        ) from e


@router.patch("/glossary-entries/{glossary_entry_id}", response_model=schemas.GlossaryEntry)
def update_glossary_entry(
    glossary_entry_id: uuid.UUID,
    request: schemas.UpdateGlossaryEntry,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update a glossary entry.

    Raises:
        404: Entry not found.
        400: Field value too long.
    """
    try:
        return modify_glossary_entry(db, glossary_entry_id, request, current_user)
    except GlossaryEntryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary entry with id {glossary_entry_id} not found.",
        ) from e
    except DataTooLongException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A field value is too long.",
        ) from e


@router.delete("/glossary-entries/{glossary_entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_glossary_entry(
    glossary_entry_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Delete a glossary entry.

    Raises:
        404: Entry not found.
    """
    try:
        remove_glossary_entry(db, glossary_entry_id, current_user)
    except GlossaryEntryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary entry with id {glossary_entry_id} not found.",
        ) from e


# --- Glossary Contributors ---


@router.get("/glossaries/{glossary_id}/contributors", response_model=list[schemas.GlossaryContributor])
def read_glossary_contributors(
    glossary_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    List contributors for a glossary.

    Raises:
        404: Glossary not found.
    """
    try:
        return query_glossary_contributors(db, glossary_id, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary with id {glossary_id} not found.",
        ) from e


@router.post(
    "/glossaries/{glossary_id}/contributors",
    response_model=schemas.GlossaryContributor,
    status_code=status.HTTP_201_CREATED,
)
def create_glossary_contributor(
    glossary_id: uuid.UUID,
    request: schemas.AddGlossaryContributor,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Add a contributor to a glossary (owner only).

    Raises:
        404: Glossary not found or insufficient permissions.
        409: User is already a contributor.
    """
    try:
        return insert_glossary_contributor(db, glossary_id, request, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary with id {glossary_id} not found.",
        ) from e
    except DuplicateGlossaryContributorException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a contributor to this glossary.",
        ) from e


@router.patch("/glossaries/{glossary_id}/contributors/{user_id}", response_model=schemas.GlossaryContributor)
def update_glossary_contributor(
    glossary_id: uuid.UUID,
    user_id: uuid.UUID,
    request: schemas.UpdateGlossaryContributor,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Update a contributor's role (owner only).

    Raises:
        404: Contributor not found or insufficient permissions.
    """
    try:
        return modify_glossary_contributor(db, glossary_id, user_id, request, current_user)
    except GlossaryContributorNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contributor not found.",
        ) from e


@router.delete("/glossaries/{glossary_id}/contributors/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_glossary_contributor(
    glossary_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Remove a contributor (owner only).

    Raises:
        404: Contributor not found or insufficient permissions.
    """
    try:
        remove_glossary_contributor(db, glossary_id, user_id, current_user)
    except GlossaryContributorNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contributor not found.",
        ) from e


# --- Import from Labels ---


@router.post("/glossaries/{glossary_id}/import-from-labels", response_model=schemas.ImportResult)
def action_import_from_labels(
    glossary_id: uuid.UUID,
    request: schemas.ImportFromLabels,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Populate glossary entries from a label group.

    Raises:
        404: Glossary or label group not found.
    """
    try:
        return import_from_labels(db, glossary_id, request, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary with id {glossary_id} not found.",
        ) from e
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e) or "Label group not found.",
        ) from e
    except UnknownError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from e


# --- Term Search ---


@router.post("/glossary-entries/{glossary_entry_id}/search-occurrences", response_model=schemas.SearchTermResponse)
def read_term_occurrences(
    glossary_entry_id: uuid.UUID,
    request: schemas.SearchTermRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    """
    Search for occurrences of a glossary entry's source_term across chapters.

    Two modes:
    - 'string': Searches the primary revision text for each chapter using string matching.
    - 'label': Searches labels where label_word matches the source_term within a label group.

    Raises:
        404: Glossary entry not found or label group not found (label mode).
        400: Invalid request (e.g. label_group_id missing in label mode).
    """
    try:
        return search_term_occurrences(db, glossary_entry_id, request, current_user)
    except GlossaryEntryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary entry with id {glossary_entry_id} not found.",
        ) from e
    except InvalidSearchModeException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e) or "Label group not found.",
        ) from e


# --- Translation Jobs ---


@router.post(
    "/glossaries/{glossary_id}/translate",
    response_model=schemas.GlossaryTranslationJob,
    status_code=status.HTTP_201_CREATED,
)
async def action_translate_glossary(
    glossary_id: uuid.UUID,
    request: schemas.CreateTranslationJob,
    db: Annotated[Session, Depends(get_db)],
    dispatcher: Annotated[TranslationDispatcher, Depends(get_translation_dispatcher)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a translation job for a glossary and enqueue it for processing.
    Requires editor or owner access to the glossary.

    Raises:
        404: Glossary not found or insufficient permissions.
        503: Queue is full.
        500: Enqueue failed or unexpected error.
    """
    try:
        job = create_translation_job(db, glossary_id, request, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary with id {glossary_id} not found.",
        ) from e
    except UnknownError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from e

    job_id_str = str(job.job_id)
    try:
        await dispatcher.enqueue(job_id_str, job.job_id, request.model_name)
    except QueueFullException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Translation queue is full. Please try again later.",
        ) from e
    except EnqueueFailedException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue translation job: {str(e)}",
        ) from e

    return job


@router.get(
    "/glossaries/{glossary_id}/translation-jobs",
    response_model=list[schemas.GlossaryTranslationJob],
)
def read_translation_jobs(
    glossary_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    List all translation jobs for a glossary.

    Raises:
        404: Glossary not found or insufficient permissions.
    """
    try:
        return query_translation_jobs(db, glossary_id, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary with id {glossary_id} not found.",
        ) from e


@router.get(
    "/glossaries/{glossary_id}/translation-jobs/{job_id}",
    response_model=schemas.GlossaryTranslationJob,
)
def read_translation_job(
    glossary_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get a single translation job by id.

    Raises:
        404: Glossary or translation job not found.
    """
    try:
        return query_translation_job(db, glossary_id, job_id, current_user)
    except GlossaryNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Glossary with id {glossary_id} not found.",
        ) from e
    except GlossaryTranslationJobNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translation job with id {job_id} not found.",
        ) from e
