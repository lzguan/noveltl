import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from src.requests.cache import redis_cache
from src.requests.decorators import attl_cache
from src.schemas import DetailHTTPErrorResponse, RequestConflictErrorResponse

from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..database import get_db
from . import schemas
from .dependencies import get_arq_dispatcher
from .exceptions import AutoLabelDuplicateException, AutoLabelNotFoundException
from .service import (
    insert_auto_labels,
    query_auto_label_by_id,
    query_auto_label_runs,
    query_auto_labels_by_run,
)
from .utils import AutoLabelDispatcher

router = APIRouter()


@router.get("/auto-label-runs", response_model=list[schemas.AutoLabelRun])
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
    response_model=list[schemas.AutoLabelMeta],
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


@router.get("/auto-labels/{autoLabelId}", response_model=schemas.AutoLabel)
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
    response_model=schemas.CreateAutoLabelsResponse,
    responses={
        400: {"model": DetailHTTPErrorResponse, "description": "Invalid request data."},
        409: {"model": RequestConflictErrorResponse, "description": "Request key conflict."},
    },
)
@attl_cache(cache=redis_cache, ttl=60)
async def create_autolabels(
    request: schemas.CreateAutoLabels,
    db: Annotated[Session, Depends(get_db)],
    dispatcher: Annotated[AutoLabelDispatcher, Depends(get_arq_dispatcher)],
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
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unknown error occured: {str(e)}",
        ) from e
