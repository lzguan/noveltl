import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.exceptions import UserNotFoundException
from src.auth.models import User
from src.database import get_async_db
from src.exceptions import InsufficientPermissionsException
from src.novels.exceptions import NovelNotFoundException
from src.publishing import schemas, service
from src.publishing.client import ReaderClient
from src.publishing.dependencies import get_publish_dispatcher, get_reader_client
from src.publishing.dispatch import PublishDispatcher
from src.publishing.exceptions import (
    InvalidTargetUrlException,
    KeyDecryptionException,
    LastTargetOwnerException,
    PublishEnqueueFailedException,
    PublishingNotConfiguredException,
    PublishJobAlreadyActiveException,
    PublishJobNotFoundException,
    TargetConnectionException,
    TargetMemberNotFoundException,
    TargetNotFoundException,
    TargetPermissionException,
)
from src.schemas import OperationStatus

router = APIRouter(tags=["publishing"])

type DB = Annotated[AsyncSession, Depends(get_async_db)]
type CurrentUser = Annotated[User, Depends(get_current_user)]
type ReaderClientDep = Annotated[ReaderClient, Depends(get_reader_client)]
type PublishDispatcherDep = Annotated[PublishDispatcher, Depends(get_publish_dispatcher)]
type TargetId = Annotated[uuid.UUID, Path(alias="targetId")]
type NovelId = Annotated[uuid.UUID, Path(alias="novelId")]
type JobId = Annotated[uuid.UUID, Path(alias="jobId")]
type UserId = Annotated[uuid.UUID, Path(alias="userId")]


@router.get("/publishing/targets", response_model=list[schemas.PublishingTargetRead])
async def read_publishing_targets(
    db: DB,
    current_user: CurrentUser,
) -> list[schemas.PublishingTargetRead]:
    return await service.list_targets(db, current_user)


@router.post(
    "/publishing/targets",
    response_model=schemas.PublishingTargetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_publishing_target(
    request: schemas.CreatePublishingTarget,
    db: DB,
    current_user: CurrentUser,
    reader_client: ReaderClientDep,
) -> schemas.PublishingTargetRead:
    try:
        return await service.create_target(db, current_user, request, reader_client)
    except InvalidTargetUrlException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except PublishingNotConfiguredException as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except TargetConnectionException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post("/publishing/targets/{targetId}/test", response_model=schemas.PublishingTargetTestResult)
async def test_publishing_target(
    target_id: TargetId,
    db: DB,
    current_user: CurrentUser,
    reader_client: ReaderClientDep,
) -> schemas.PublishingTargetTestResult:
    try:
        return await service.test_target(db, current_user, target_id, reader_client)
    except TargetNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing target not found.") from e
    except TargetPermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except InvalidTargetUrlException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except PublishingNotConfiguredException as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except KeyDecryptionException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
    except TargetConnectionException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.patch("/publishing/targets/{targetId}", response_model=schemas.PublishingTargetRead)
async def update_publishing_target(
    target_id: TargetId,
    request: schemas.UpdatePublishingTarget,
    db: DB,
    current_user: CurrentUser,
    reader_client: ReaderClientDep,
) -> schemas.PublishingTargetRead:
    try:
        return await service.update_target(db, current_user, target_id, request, reader_client)
    except TargetNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing target not found.") from e
    except TargetPermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except InvalidTargetUrlException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except PublishingNotConfiguredException as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except KeyDecryptionException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
    except TargetConnectionException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.delete("/publishing/targets/{targetId}", response_model=OperationStatus)
async def delete_publishing_target(
    target_id: TargetId,
    db: DB,
    current_user: CurrentUser,
) -> OperationStatus:
    try:
        return await service.delete_target(db, current_user, target_id)
    except TargetNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing target not found.") from e
    except TargetPermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.get(
    "/publishing/targets/{targetId}/members",
    response_model=list[schemas.PublishingTargetMemberRead],
)
async def read_publishing_target_members(
    target_id: TargetId,
    db: DB,
    current_user: CurrentUser,
) -> list[schemas.PublishingTargetMemberRead]:
    try:
        return await service.list_target_members(db, current_user, target_id)
    except TargetNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing target not found.") from e
    except TargetPermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.post(
    "/publishing/targets/{targetId}/members",
    response_model=schemas.PublishingTargetMemberRead,
)
async def upsert_publishing_target_member(
    target_id: TargetId,
    request: schemas.UpsertPublishingTargetMember,
    db: DB,
    current_user: CurrentUser,
) -> schemas.PublishingTargetMemberRead:
    try:
        return await service.upsert_target_member(db, current_user, target_id, request)
    except TargetNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing target not found.") from e
    except UserNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from e
    except TargetPermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except LastTargetOwnerException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete(
    "/publishing/targets/{targetId}/members/{userId}",
    response_model=OperationStatus,
)
async def delete_publishing_target_member(
    target_id: TargetId,
    user_id: UserId,
    db: DB,
    current_user: CurrentUser,
) -> OperationStatus:
    try:
        return await service.remove_target_member(db, current_user, target_id, user_id)
    except TargetNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing target not found.") from e
    except TargetMemberNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target member not found.") from e
    except TargetPermissionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except LastTargetOwnerException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/novels/{novelId}/publish/status", response_model=schemas.NovelPublishStatus)
async def read_novel_publish_status(
    novel_id: NovelId,
    target_id: Annotated[uuid.UUID, Query(alias="targetId")],
    db: DB,
    current_user: CurrentUser,
    reader_client: ReaderClientDep,
) -> schemas.NovelPublishStatus:
    try:
        return await service.get_novel_publish_status(db, current_user, novel_id, target_id, reader_client)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found.") from e
    except TargetNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing target not found.") from e
    except (InsufficientPermissionsException, TargetPermissionException) as e:
        detail = str(e) or "Insufficient permissions."
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from e
    except InvalidTargetUrlException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except PublishingNotConfiguredException as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except KeyDecryptionException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
    except TargetConnectionException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post(
    "/novels/{novelId}/publish",
    response_model=schemas.PublishJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_novel_publish(
    novel_id: NovelId,
    request: schemas.StartPublishRequest,
    db: DB,
    current_user: CurrentUser,
    dispatcher: PublishDispatcherDep,
) -> schemas.PublishJobRead:
    try:
        return await service.start_publish_job(db, current_user, novel_id, request, dispatcher)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found.") from e
    except TargetNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing target not found.") from e
    except (InsufficientPermissionsException, TargetPermissionException) as e:
        detail = str(e) or "Insufficient permissions."
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from e
    except PublishJobAlreadyActiveException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except PublishEnqueueFailedException as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e


@router.get("/novels/{novelId}/publish/jobs", response_model=list[schemas.PublishJobRead])
async def read_novel_publish_jobs(
    novel_id: NovelId,
    db: DB,
    current_user: CurrentUser,
    target_id: Annotated[uuid.UUID | None, Query(alias="targetId")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[schemas.PublishJobRead]:
    try:
        return await service.list_publish_jobs(db, current_user, novel_id, target_id=target_id, limit=limit)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found.") from e
    except TargetNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publishing target not found.") from e
    except (InsufficientPermissionsException, TargetPermissionException) as e:
        detail = str(e) or "Insufficient permissions."
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from e


@router.get("/novels/{novelId}/publish/jobs/{jobId}", response_model=schemas.PublishJobRead)
async def read_novel_publish_job(
    novel_id: NovelId,
    job_id: JobId,
    db: DB,
    current_user: CurrentUser,
) -> schemas.PublishJobRead:
    try:
        return await service.get_publish_job(db, current_user, novel_id, job_id)
    except NovelNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found.") from e
    except PublishJobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publish job not found.") from e
    except InsufficientPermissionsException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.") from e
