from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_optional_user
from src.auth.models import User
from src.database import get_db
from src.memory.exceptions import ConventionNotFoundException, MemoryGroupNotFoundException
from src.memory.plugins.conventions.schemas import ConventionPage, ConventionRead, SaveConvention
from src.memory.plugins.conventions.service import (
    change_convention_review_status,
    create_convention,
    delete_convention,
    query_conventions,
    update_convention,
)
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.schemas import UpdateReviewStatus
from src.memory.types import ReviewStatus
from src.schemas import DetailHTTPErrorResponse

router = APIRouter(prefix="/memory-groups/{memoryGroupId}/conventions")


@router.get("", response_model=ConventionPage)
def read_conventions(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    category: ConventionCategory | None = None,
    review_statuses: Annotated[list[ReviewStatus] | None, Query(alias="reviewStatuses")] = None,
):
    return query_conventions(
        db, current_user, memory_group_id, skip, limit, category=category, review_statuses=review_statuses
    )


@router.post(
    "",
    response_model=ConventionRead,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def add_convention(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    request: SaveConvention,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return create_convention(db, current_user, memory_group_id, request)
    except MemoryGroupNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory group not found.") from exc


@router.put("/{conventionId}", response_model=ConventionRead, responses={404: {"model": DetailHTTPErrorResponse}})
def put_convention(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    convention_id: Annotated[UUID, Path(alias="conventionId")],
    request: SaveConvention,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return update_convention(db, current_user, memory_group_id, convention_id, request)
    except ConventionNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convention not found.") from exc


@router.patch(
    "/{conventionId}/review-status",
    response_model=ConventionRead,
    responses={404: {"model": DetailHTTPErrorResponse}},
)
def edit_convention_review_status(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    convention_id: Annotated[UUID, Path(alias="conventionId")],
    request: UpdateReviewStatus,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return change_convention_review_status(db, current_user, memory_group_id, convention_id, request.review_status)
    except ConventionNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convention not found.") from exc


@router.delete(
    "/{conventionId}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"model": DetailHTTPErrorResponse}}
)
def remove_convention(
    memory_group_id: Annotated[UUID, Path(alias="memoryGroupId")],
    convention_id: Annotated[UUID, Path(alias="conventionId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    try:
        delete_convention(db, current_user, memory_group_id, convention_id)
    except ConventionNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convention not found.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
