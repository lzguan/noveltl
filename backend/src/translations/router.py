from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_async_db
from src.translations.metadata import check_pipeline, read_action_metadata
from src.translations.outputs import (
    TranslationConflictError,
    accept_translation_outputs,
    list_translation_outputs,
    read_translation_output,
)
from src.translations.pipeline_schemas import TranslationPipelineCheck
from src.translations.schemas import (
    TranslationAcceptRequest,
    TranslationAcceptResult,
    TranslationActionsRead,
    TranslationBatchPage,
    TranslationControlResult,
    TranslationJobCreate,
    TranslationJobCreated,
    TranslationJobCreateRequest,
    TranslationJobDraft,
    TranslationJobPage,
    TranslationJobRead,
    TranslationOutputChapterDetail,
    TranslationOutputsRead,
)
from src.translations.service import (
    Control,
    TranslationNotFoundError,
    control_translation_job,
    create_translation_job,
    read_translation_job,
)
from src.translations.viewer import list_translation_jobs, read_translation_batches

router = APIRouter(prefix="/translation-jobs", tags=["translations"])
type DB = Annotated[AsyncSession, Depends(get_async_db)]
type CurrentUser = Annotated[User, Depends(get_current_user)]
type JobId = Annotated[UUID, Path(alias="jobId")]
type BatchId = Annotated[UUID, Path(alias="batchId")]
type ChapterId = Annotated[UUID, Path(alias="chapterId")]


@router.post("", response_model=TranslationJobCreated, status_code=201)
async def create(request: TranslationJobCreateRequest, db: DB, current_user: CurrentUser) -> TranslationJobCreated:
    try:
        validated = TranslationJobCreate.model_validate(request.model_dump())
    except ValidationError as error:
        errors = [{**item, "loc": ("body", *item["loc"])} for item in error.errors()]
        raise RequestValidationError(errors, body=request.model_dump()) from error
    try:
        return TranslationJobCreated(job_id=await create_translation_job(db, current_user, validated))
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get("/actions", response_model=TranslationActionsRead)
def list_actions(current_user: CurrentUser) -> TranslationActionsRead:
    """Return action compatibility and standalone configuration JSON Schemas."""
    return read_action_metadata()


@router.post("/check", response_model=TranslationPipelineCheck)
def check(draft: TranslationJobDraft, current_user: CurrentUser) -> TranslationPipelineCheck:
    return check_pipeline(draft)


@router.get("", response_model=TranslationJobPage)
async def list_jobs(
    db: DB,
    current_user: CurrentUser,
    novel_id: Annotated[UUID, Query(alias="novelId")],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> TranslationJobPage:
    try:
        return await list_translation_jobs(db, current_user, novel_id, offset=offset, limit=limit)
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/{jobId}/batches", response_model=TranslationBatchPage)
async def list_batches(
    job_id: JobId,
    db: DB,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
) -> TranslationBatchPage:
    try:
        return await read_translation_batches(db, current_user, job_id, offset=offset, limit=limit)
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/{jobId}/outputs", response_model=TranslationOutputsRead)
async def list_outputs(
    job_id: JobId,
    db: DB,
    current_user: CurrentUser,
    stage_id: Annotated[UUID | None, Query(alias="stageId")] = None,
) -> TranslationOutputsRead:
    try:
        return await list_translation_outputs(db, current_user, job_id, stage_id=stage_id)
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/{jobId}/outputs/{chapterId}", response_model=TranslationOutputChapterDetail)
async def read_output(
    job_id: JobId,
    chapter_id: ChapterId,
    db: DB,
    current_user: CurrentUser,
    stage_id: Annotated[UUID | None, Query(alias="stageId")] = None,
) -> TranslationOutputChapterDetail:
    try:
        return await read_translation_output(db, current_user, job_id, chapter_id, stage_id=stage_id)
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error


@router.post("/{jobId}/accept", response_model=TranslationAcceptResult)
async def accept_outputs(
    job_id: JobId, request: TranslationAcceptRequest, db: DB, current_user: CurrentUser
) -> TranslationAcceptResult:
    try:
        return await accept_translation_outputs(db, current_user, job_id, request)
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except TranslationConflictError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/{jobId}", response_model=TranslationJobRead)
async def read(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationJobRead:
    try:
        return await read_translation_job(db, current_user, job_id)
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error


async def _control(
    db: AsyncSession, user: User, job_id: UUID, operation: Control, batch_id: UUID | None = None
) -> TranslationControlResult:
    try:
        return await control_translation_job(db, user, job_id, operation, batch_id=batch_id)
    except TranslationNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.post("/{jobId}/start", response_model=TranslationControlResult)
async def start(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return await _control(db, current_user, job_id, "start")


@router.post("/{jobId}/resume-all", response_model=TranslationControlResult)
async def resume_all(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return await _control(db, current_user, job_id, "resume")


@router.post("/{jobId}/cancel-all", response_model=TranslationControlResult)
async def cancel_all(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return await _control(db, current_user, job_id, "cancel")


@router.post("/{jobId}/retry-all", response_model=TranslationControlResult)
async def retry_all(job_id: JobId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return await _control(db, current_user, job_id, "retry")


@router.post("/{jobId}/batches/{batchId}/cancel", response_model=TranslationControlResult)
async def cancel(job_id: JobId, batch_id: BatchId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return await _control(db, current_user, job_id, "cancel", batch_id)


@router.post("/{jobId}/batches/{batchId}/retry", response_model=TranslationControlResult)
async def retry(job_id: JobId, batch_id: BatchId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return await _control(db, current_user, job_id, "retry", batch_id)


@router.post("/{jobId}/batches/{batchId}/start", response_model=TranslationControlResult)
async def start_batch(job_id: JobId, batch_id: BatchId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return await _control(db, current_user, job_id, "start", batch_id)


@router.post("/{jobId}/batches/{batchId}/resume", response_model=TranslationControlResult)
async def resume_batch(job_id: JobId, batch_id: BatchId, db: DB, current_user: CurrentUser) -> TranslationControlResult:
    return await _control(db, current_user, job_id, "resume", batch_id)
