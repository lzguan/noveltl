import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.autolabels.dependencies import get_dispatcher
from src.autolabels.exceptions import AutoLabelDuplicateException, AutoLabelNotFoundException
from src.autolabels.inference.dispatch.dispatcher import AutoLabelDispatcher
from src.autolabels.promotions.service import insert_label_datas_by_autolabels
from src.autolabels.schemas import (
    AutoLabel,
    AutoLabelMetaWithCid,
    AutoLabelRun,
    CreateAutoLabels,
    CreateAutoLabelsResponse,
    CreateLabelDataByAutoLabel,
    CreateLabelDataByAutoLabelStatus,
)
from src.autolabels.service import (
    insert_auto_labels,
    query_auto_label_by_id,
    query_auto_label_runs,
    query_auto_labels_by_run,
)
from src.database import get_async_db, get_db
from src.labels.exceptions import LabelGroupNotFoundException
from src.novels.exceptions import NovelNotFoundException
from src.requests.cache import redis_cache
from src.requests.decorators import attl_cache, serialize_response_model
from src.schemas import DetailHTTPErrorResponse, RequestConflictErrorResponse

router = APIRouter()


@router.get("/auto-label-runs", response_model=list[AutoLabelRun])
async def read_auto_label_runs(
    novel_id: Annotated[uuid.UUID, Query(alias="novelId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    mine: bool = False,
):
    """
    List autolabel runs for a novel.

    Args:
        novel_id: UUID of novel to query runs for.
        mine: If true, only return runs triggered by the current user.
    """
    return query_auto_label_runs(db, current_user, novel_id, mine)


@router.get(
    "/auto-label-runs/{runId}/auto-labels",
    response_model=list[AutoLabelMetaWithCid],
)
async def read_auto_labels_by_run(
    run_id: Annotated[uuid.UUID, Path(alias="runId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    start: int | None = None,
    end: int | None = None,
):
    """
    Get autolabel metadata for all autolabels in a run.

    Args:
        run_id: UUID of the run.
        start: Optional inclusive lower bound on chapter number.
        end: Optional exclusive upper bound on chapter number.
    """
    return query_auto_labels_by_run(db, current_user, run_id, start, end)


@router.get("/auto-labels/{autoLabelId}", response_model=AutoLabel)
async def read_autolabel_by_id(
    auto_label_id: Annotated[uuid.UUID, Path(alias="autoLabelId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Retrieve a single autolabel with its label data.

    Args:
        auto_label_id: UUID of the autolabel.
    """
    try:
        autolabel = query_auto_label_by_id(db, current_user, auto_label_id)
    except AutoLabelNotFoundException as e:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No autolabel with id {auto_label_id} found.",
        ) from e
    return autolabel


@router.post(
    "/auto-labels",
    response_model=CreateAutoLabelsResponse,
    responses={
        400: {"model": DetailHTTPErrorResponse, "description": "Invalid request data."},
        404: {"model": DetailHTTPErrorResponse, "description": "Novel not found or inaccessible."},
        409: {"model": RequestConflictErrorResponse, "description": "Request key conflict."},
    },
)
@attl_cache(cache=redis_cache, ttl=60, serialize_ret=serialize_response_model(CreateAutoLabelsResponse))
async def create_autolabels(
    request: CreateAutoLabels,
    db: Annotated[Session, Depends(get_db)],
    dispatcher: Annotated[AutoLabelDispatcher, Depends(get_dispatcher)],
    current_user: Annotated[User, Depends(get_current_user)],
    request_key: Annotated[uuid.UUID | None, Query(alias="requestKey")] = None,
):
    """
    Create a new autolabel run and autolabels for matching chapters.

    The run is created first, then autolabel entries are inserted for each
    matching chapter. Worker tasks are dispatched for each autolabel.
    """
    try:
        return await insert_auto_labels(db, current_user, dispatcher, request)
    except AutoLabelDuplicateException as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="An unexpected error occurred, likely because you tried creating auto labels at the same time as someone else.",
        ) from e
    except NovelNotFoundException as e:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unknown error occured.",
        ) from e


@router.post(
    "/label-groups/{labelGroupId}/label-datas/auto-labels",
    response_model=CreateLabelDataByAutoLabelStatus,
    responses={
        404: {"model": DetailHTTPErrorResponse, "description": "Label group not found."},
        409: {
            "model": RequestConflictErrorResponse,
            "description": "Request key conflict.",
        },
    },
)
@attl_cache(
    ttl=3600,
    cache=redis_cache,
    serialize_ret=serialize_response_model(CreateLabelDataByAutoLabelStatus),
)
async def create_label_datas_by_auto_labels(
    label_group_id: Annotated[uuid.UUID, Path(alias="labelGroupId")],
    request: CreateLabelDataByAutoLabel,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request_key: Annotated[uuid.UUID | None, Query(alias="requestKey")] = None,
):
    """
    Creates label datas and populates labels from autolabel results.
    """
    try:
        return await insert_label_datas_by_autolabels(db, current_user, label_group_id, request)
    except LabelGroupNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label group {label_group_id} not found or not accessible.",
        ) from e
