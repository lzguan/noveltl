from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.memory.agent.dispatch.dependencies import get_dispatcher
from src.memory.agent.dispatch.dispatcher import MemoryAgentDispatcher
from src.memory.agent.schemas import CreateMemoryJob, MemoryChapterTask, MemoryChapterTaskPage, MemoryJob
from src.memory.agent.service import (
    abort_job,
    create_job,
    delete_job,
    delete_task,
    query_job,
    query_jobs,
    query_task,
    query_tasks,
    retry_task,
    start_job,
    start_task,
)
from src.memory.exceptions import (
    MemoryAgentEnqueueFailedException,
    MemoryChapterTaskNotFoundException,
    MemoryChapterTaskStateException,
    MemoryGroupNotFoundException,
    MemoryJobNotFoundException,
    MemoryJobStateException,
)
from src.schemas import DetailHTTPErrorResponse

router = APIRouter(prefix="/memory-agent")


@router.post(
    "/jobs",
    response_model=MemoryJob,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def add_memory_job(
    request: CreateMemoryJob,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MemoryJob:
    try:
        return create_job(
            db,
            current_user,
            request.memory_group_id,
            request.start_chapter_num,
            request.end_chapter_num,
            request.params,
        )
    except MemoryGroupNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/jobs",
    response_model=list[MemoryJob],
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_memory_jobs(
    memory_group_id: Annotated[UUID, Query(alias="memoryGroupId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[MemoryJob]:
    try:
        return query_jobs(db, current_user, memory_group_id)
    except MemoryGroupNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/jobs/{memoryJobId}",
    response_model=MemoryJob,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_memory_job(
    memory_job_id: Annotated[UUID, Path(alias="memoryJobId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MemoryJob:
    try:
        return query_job(db, current_user, memory_job_id)
    except MemoryJobNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/jobs/{memoryJobId}/tasks",
    response_model=MemoryChapterTaskPage,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_memory_tasks(
    memory_job_id: Annotated[UUID, Path(alias="memoryJobId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> MemoryChapterTaskPage:
    try:
        return query_tasks(db, current_user, memory_job_id, skip, limit)
    except MemoryJobNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/jobs/{memoryJobId}/tasks/{chapterId}",
    response_model=MemoryChapterTask,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def read_memory_task(
    memory_job_id: Annotated[UUID, Path(alias="memoryJobId")],
    chapter_id: Annotated[UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MemoryChapterTask:
    try:
        return query_task(db, current_user, memory_job_id, chapter_id)
    except MemoryChapterTaskNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/jobs/{memoryJobId}/start",
    response_model=MemoryJob,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
        503: {"model": DetailHTTPErrorResponse},
    },
)
def start_memory_job(
    memory_job_id: Annotated[UUID, Path(alias="memoryJobId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[MemoryAgentDispatcher, Depends(get_dispatcher)],
) -> MemoryJob:
    try:
        return start_job(db, current_user, dispatcher, memory_job_id)
    except MemoryJobNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MemoryJobStateException as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MemoryAgentEnqueueFailedException as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post(
    "/jobs/{memoryJobId}/abort",
    response_model=MemoryJob,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def abort_memory_job(
    memory_job_id: Annotated[UUID, Path(alias="memoryJobId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MemoryJob:
    try:
        return abort_job(db, current_user, memory_job_id)
    except MemoryJobNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/jobs/{memoryJobId}/tasks/{chapterId}/start",
    response_model=MemoryChapterTask,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
        503: {"model": DetailHTTPErrorResponse},
    },
)
def start_memory_task(
    memory_job_id: Annotated[UUID, Path(alias="memoryJobId")],
    chapter_id: Annotated[UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[MemoryAgentDispatcher, Depends(get_dispatcher)],
) -> MemoryChapterTask:
    try:
        return start_task(db, current_user, dispatcher, memory_job_id, chapter_id)
    except MemoryChapterTaskNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MemoryChapterTaskStateException as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MemoryAgentEnqueueFailedException as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post(
    "/jobs/{memoryJobId}/tasks/{chapterId}/retry",
    response_model=MemoryChapterTask,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
        503: {"model": DetailHTTPErrorResponse},
    },
)
def retry_memory_task(
    memory_job_id: Annotated[UUID, Path(alias="memoryJobId")],
    chapter_id: Annotated[UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[MemoryAgentDispatcher, Depends(get_dispatcher)],
) -> MemoryChapterTask:
    try:
        return retry_task(db, current_user, dispatcher, memory_job_id, chapter_id)
    except MemoryChapterTaskNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MemoryChapterTaskStateException as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except MemoryAgentEnqueueFailedException as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.delete(
    "/jobs/{memoryJobId}/tasks/{chapterId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
    },
)
def remove_memory_task(
    memory_job_id: Annotated[UUID, Path(alias="memoryJobId")],
    chapter_id: Annotated[UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    try:
        delete_task(db, current_user, memory_job_id, chapter_id)
    except MemoryChapterTaskNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MemoryChapterTaskStateException as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/jobs/{memoryJobId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": DetailHTTPErrorResponse},
        409: {"model": DetailHTTPErrorResponse},
    },
)
def remove_memory_job(
    memory_job_id: Annotated[UUID, Path(alias="memoryJobId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    try:
        delete_job(db, current_user, memory_job_id)
    except MemoryJobNotFoundException as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MemoryJobStateException as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
