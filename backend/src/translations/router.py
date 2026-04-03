import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..database import get_db
from ..exceptions import UnknownError
from ..novels.exceptions import NovelNotFoundException
from . import schemas
from .dependencies import get_translation_dispatcher
from .exceptions import (
    NovelTranslationJobNotFoundException,
    TranslationEnqueueFailedException,
    TranslationQueueFullException,
)
from .service import (
    insert_translation_job,
    query_translation_job,
    query_translation_jobs,
)
from .utils import TranslationDispatcher

router = APIRouter()


@router.post("/translations", response_model=schemas.NovelTranslationJob, status_code=status.HTTP_201_CREATED)
async def create_translation_job(
    request: schemas.CreateNovelTranslationJob,
    db: Annotated[Session, Depends(get_db)],
    dispatcher: Annotated[TranslationDispatcher, Depends(get_translation_dispatcher)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Create a novel translation job and enqueue it for background processing.
    Requires editor or owner access to the source novel.

    Raises:
        404: Source novel not found or insufficient permissions.
        503: Translation queue is full.
        500: Enqueue failed or unexpected error.
    """
    try:
        job = insert_translation_job(db, current_user, request)
    except NovelNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source novel not found.",
        ) from e
    except UnknownError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        ) from e

    job_id_str = str(job.job_id)
    try:
        await dispatcher.enqueue(
            job_id_str,
            job.job_id,
            request.source_novel_id,
            request.target_language_code,
            request.glossary_id,
            request.model_name,
        )
    except TranslationQueueFullException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Translation queue is full. Please try again later.",
        ) from e
    except TranslationEnqueueFailedException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue translation job: {str(e)}",
        ) from e

    return job


@router.get("/translations/{job_id}", response_model=schemas.NovelTranslationJobWithMappings)
def read_translation_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get a single translation job by id, including chapter mappings.

    Raises:
        404: Job not found or insufficient permissions.
    """
    try:
        return query_translation_job(db, current_user, job_id)
    except NovelTranslationJobNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translation job with id {job_id} not found.",
        ) from e


@router.get("/translations", response_model=list[schemas.NovelTranslationJob])
def read_translation_jobs(
    source_novel_id: Annotated[uuid.UUID, Query(alias="source-novel-id")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    List all translation jobs for a source novel.
    Requires contributor access to the source novel.

    Raises:
        404: Source novel not found or insufficient permissions.
    """
    return query_translation_jobs(db, current_user, source_novel_id)
