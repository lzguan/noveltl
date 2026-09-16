from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.translations.schemas import (
    TranslationControlResult,
    TranslationJobCreate,
    TranslationJobCreated,
    TranslationJobRead,
)
from src.translations.service import (
    Control,
    TranslationNotFoundError,
    control_translation_job,
    create_translation_job,
    read_translation_job,
)

router = APIRouter(prefix="/translation-jobs", tags=["translations"])
type DB = Annotated[Session, Depends(get_db)]
type CurrentUser = Annotated[User, Depends(get_current_user)]
type JobId = Annotated[UUID, Path(alias="jobId")]
type BatchId = Annotated[UUID, Path(alias="batchId")]


@router.post("", response_model=TranslationJobCreated, status_code=201)
def create(request: TranslationJobCreate, db: DB, current_user: CurrentUser) -> TranslationJobCreated:
    try:
        return TranslationJobCreated(job_id=create_translation_job(db, current_user, request))
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get("/{jobId}", response_model=TranslationJobRead)
def read(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationJobRead:
    try:
        return read_translation_job(db, current_user, job_id)
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error


def _control(
    db: Session, user: User, job_id: UUID, operation: Control, batch_id: UUID | None = None
) -> TranslationControlResult:
    try:
        return control_translation_job(db, user, job_id, operation, batch_id=batch_id)
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.post("/{jobId}/start", response_model=TranslationControlResult)
def start(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return _control(db, current_user, job_id, "start")


@router.post("/{jobId}/resume-all", response_model=TranslationControlResult)
def resume_all(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return _control(db, current_user, job_id, "resume")


@router.post("/{jobId}/cancel-all", response_model=TranslationControlResult)
def cancel_all(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return _control(db, current_user, job_id, "cancel")


@router.post("/{jobId}/retry-all", response_model=TranslationControlResult)
def retry_all(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return _control(db, current_user, job_id, "retry")


@router.post("/{jobId}/batches/{batchId}/cancel", response_model=TranslationControlResult)
def cancel(job_id: JobId, batch_id: BatchId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return _control(db, current_user, job_id, "cancel", batch_id)


@router.post("/{jobId}/batches/{batchId}/retry", response_model=TranslationControlResult)
def retry(job_id: JobId, batch_id: BatchId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return _control(db, current_user, job_id, "retry", batch_id)
