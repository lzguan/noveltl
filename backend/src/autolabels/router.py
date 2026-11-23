import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.autolabels.constants import MAX_POLLED_PROMOTIONS
from src.autolabels.dependencies import get_dispatcher, get_promotion_dispatcher
from src.autolabels.exceptions import (
    AutoLabelDuplicateException,
    AutoLabelNotFoundException,
    PromotionAlreadyActiveException,
)
from src.autolabels.inference.dispatch.dispatcher import AutoLabelDispatcher
from src.autolabels.promotions.dispatch.dispatcher import PromotionDispatcher
from src.autolabels.schemas import (
    AutoLabel,
    AutoLabelMetaWithCid,
    AutoLabelRun,
    CreateAutoLabels,
    CreateAutoLabelsResponse,
    CreatedLabelPromotion,
    CreateLabelDataByAutoLabel,
    LabelPromotionFailure,
    LabelPromotionJob,
)
from src.autolabels.service import (
    create_promotion_job,
    insert_auto_labels,
    query_auto_label_by_id,
    query_auto_label_runs,
    query_auto_labels_by_run,
    query_promotion_failures,
    query_promotion_jobs,
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
    "/label-groups/{labelGroupId}/label-promotions",
    response_model=CreatedLabelPromotion,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": DetailHTTPErrorResponse, "description": "Label group or run not found, or not editable."},
        409: {"model": DetailHTTPErrorResponse, "description": "A promotion for this run and group is running."},
    },
)
async def create_label_promotion(
    label_group_id: Annotated[uuid.UUID, Path(alias="labelGroupId")],
    request: CreateLabelDataByAutoLabel,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dispatcher: Annotated[PromotionDispatcher, Depends(get_promotion_dispatcher)],
):
    """
    Start promoting an autolabel run's labels into a label group in the background.
    """
    try:
        return await create_promotion_job(db, current_user, dispatcher, label_group_id, request)
    except LabelGroupNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except PromotionAlreadyActiveException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get(
    "/novels/{novelId}/label-promotions",
    response_model=list[LabelPromotionJob],
)
async def read_label_promotions(
    novel_id: Annotated[uuid.UUID, Path(alias="novelId")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    promotion_ids: Annotated[
        list[uuid.UUID] | None, Query(alias="promotionIds", min_length=1, max_length=MAX_POLLED_PROMOTIONS)
    ] = None,
):
    """
    List a novel's label promotion jobs: active ones first, then the most recently updated.

    With `promotionIds`, return only those jobs; ids that are missing or not readable are omitted.
    """
    return await query_promotion_jobs(db, current_user, novel_id, limit, promotion_ids)


@router.get("/label-promotions/{promotionId}/failures", response_model=list[LabelPromotionFailure])
async def read_label_promotion_failures(
    promotion_id: Annotated[uuid.UUID, Path(alias="promotionId")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    List the chapters a label promotion job could not promote, in processing order.
    """
    return await query_promotion_failures(db, current_user, promotion_id, limit, offset)
