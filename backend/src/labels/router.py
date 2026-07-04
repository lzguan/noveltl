import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..database import get_db
from ..exceptions import DataTooLongException, NotFoundException
from ..novels.exceptions import ChapterContentNotFoundException, NovelNotFoundException
from ..requests.cache import redis_cache
from ..requests.decorators import serialize_response_model, ttl_cache
from ..schemas import DetailHTTPErrorResponse, RequestConflictErrorResponse
from . import schemas
from .exceptions import (
    LabelDataNotFoundException,
    LabelDataRevisionDuplicateException,
    LabelExclusionViolationInvalidOperationException,
    LabelGroupNotFoundException,
    LabelInvalidOperationException,
    LabelNotExistsInvalidOperationException,
    LabelOutOfBoundsInvalidOperationException,
    LabelWordMismatchInvalidOperationException,
)
from .service import (
    insert_label_data,
    insert_label_datas_by_autolabels,
    insert_label_group,
    modify_label_data_by_stream,
    modify_label_group,
    query_label_contributors_of_label_group,
    query_label_data_by_id,
    query_label_datas,
    query_label_group_by_id,
    query_label_groups,
    query_label_groups_with_contributor_info,
    query_labels_by_label_data_id,
)

router = APIRouter()


@router.get("/label-groups", response_model=list[schemas.LabelGroup])
def read_label_groups(
    novel_id: Annotated[uuid.UUID, Query(alias="novelId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Gets all label groups of the current user for a novel.
    """
    return query_label_groups(db, current_user, novel_id)


@router.get("/label-groups-with-role", response_model=list[schemas.LabelGroupWithRole])
def read_label_groups_with_role(
    novel_id: Annotated[uuid.UUID, Query(alias="novelId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Gets all label groups of the current user for a novel, along with their roles.
    """
    return query_label_groups_with_contributor_info(db, current_user, novel_id)


@router.get("/label-groups/{labelGroupId}", response_model=schemas.LabelGroup)
def read_label_group(
    label_group_id: Annotated[uuid.UUID, Path(alias="labelGroupId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Gets a label group by id.

    Raises:
        404: Label group not found (or insufficient permissions).
    """
    try:
        label_group = query_label_group_by_id(db, current_user, label_group_id)
    except LabelGroupNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Label group with id {label_group_id} not found."
        ) from e
    return label_group


@router.get("/label-datas", response_model=list[schemas.LabelData])
def read_label_datas_by_group_chapters(
    label_group_id: Annotated[uuid.UUID, Query(alias="labelGroupId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    start: int | None = None,
    end: int | None = None,
):
    """
    Gets all label datas in a label group, optionally filtered by chapter range.
    """
    label_datas = query_label_datas(db, current_user, label_group_id, start, end)
    return label_datas


@router.get("/label-datas/{labelDataId}", response_model=schemas.LabelData)
def read_label_data(
    label_data_id: Annotated[uuid.UUID, Path(alias="labelDataId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Gets a label data by id.

    Raises:
        404: Label data not found (or insufficient permissions).
    """
    try:
        label_data = query_label_data_by_id(db, current_user, label_data_id)
    except LabelDataNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label data not found.") from e
    return label_data


@router.get("/label-datas/{labelDataId}/labels", response_model=list[schemas.Label])
def read_labels_by_label_data(
    label_data_id: Annotated[uuid.UUID, Path(alias="labelDataId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the specific list of labels inside a label data entry.
    """
    labels = query_labels_by_label_data_id(db, current_user, label_data_id)
    return labels


@router.get("/label-groups/{labelGroupId}/contributors", response_model=list[schemas.LabelContributor])
def read_label_contributors(
    label_group_id: Annotated[uuid.UUID, Path(alias="labelGroupId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Get the list of contributors for a label group.
    """
    try:
        contributors = query_label_contributors_of_label_group(db, current_user, label_group_id)
    except LabelGroupNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Label group with id {label_group_id} not found."
        ) from e
    return contributors


@router.post(
    "/label-groups",
    response_model=schemas.LabelGroup,
    responses={
        400: {"model": DetailHTTPErrorResponse, "description": "Label group name is too long."},
        404: {"model": DetailHTTPErrorResponse, "description": "Novel associated with this label group not found."},
        409: {
            "model": RequestConflictErrorResponse,
            "description": "Request key conflict.",
        },
    },
)
@ttl_cache(ttl=60, cache=redis_cache, success_code=200, serialize_ret=serialize_response_model(schemas.LabelGroup))
def create_label_group(
    request: schemas.CreateLabelGroup,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request_key: Annotated[uuid.UUID | None, Query(alias="requestKey")] = None,
):
    """
    Creates a new label group.

    Raises:
        404: Novel not found.
        400: Label group name is too long.
    """
    try:
        label_group = insert_label_group(db, current_user, request)
    except NovelNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Novel associated with this label group not found."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Label group name is too long.") from e
    return label_group


@router.patch("/label-groups/{labelGroupId}", response_model=schemas.LabelGroup)
def update_label_group(
    label_group_id: Annotated[uuid.UUID, Path(alias="labelGroupId")],
    request: schemas.UpdateLabelGroup,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Updates a label group (e.g. rename).

    Raises:
        404: Label group not found.
        400: Label group name is too long.
    """
    try:
        label_group = modify_label_group(db, current_user, label_group_id, request)
    except LabelGroupNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Label group with id {label_group_id} not found."
        ) from e
    except DataTooLongException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Label group name is too long.") from e
    return label_group


@router.post(
    "/label-groups/{labelGroupId}/label-datas",
    response_model=schemas.LabelData,
    responses={
        404: {"model": DetailHTTPErrorResponse, "description": "Label group or chapter content not found."},
        409: {
            "model": RequestConflictErrorResponse,
            "description": "Label data already exists for this chapter content in the label group, or the request key already exists.",
        },
    },
)
@ttl_cache(ttl=60, cache=redis_cache, success_code=200, serialize_ret=serialize_response_model(schemas.LabelData))
def create_label_data(
    label_group_id: Annotated[uuid.UUID, Path(alias="labelGroupId")],
    request: schemas.CreateLabelData,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request_key: Annotated[uuid.UUID | None, Query(alias="requestKey")] = None,
):
    """
    Creates a label data entry for a revision text in a label group.

    Raises:
        404: Label group or revision text not found.
        409: Label data for this revision text already exists in this group.
    """
    try:
        label_data = insert_label_data(db, current_user, label_group_id, request)
    except LabelGroupNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label group not found.") from e
    except LabelDataRevisionDuplicateException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Label data for this revision text already exists in this group.",
        ) from e
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Label group or revision text not found."
        ) from e
    return label_data


@router.patch(
    "/label-datas/{labelDataId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {
            "model": DetailHTTPErrorResponse,
            "description": "Operation positions are out of bounds or the operation is otherwise invalid.",
        },
        404: {
            "model": DetailHTTPErrorResponse,
            "description": "Label data, chapter content, or target label not found.",
        },
        409: {
            "model": RequestConflictErrorResponse,
            "description": "Label stream conflict, such as word mismatch, overlap violation, or request-key conflict.",
        },
    },
)
@ttl_cache(ttl=60, cache=redis_cache, success_code=204)
def update_label_data_stream(
    label_data_id: Annotated[uuid.UUID, Path(alias="labelDataId")],
    request: schemas.UpdateLabelDataStream,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request_key: Annotated[uuid.UUID | None, Query(alias="requestKey")] = None,
) -> None:
    """
    Applies a stream of edit operations to labels.

    Raises:
        404: Label data or its underlying revision text not found, or target label does not exist.
        409: Word mismatch or label overlap detected.
        400: Operation positions out of bounds or invalid operation.
    """
    try:
        modify_label_data_by_stream(db, current_user, label_data_id, request)
    except (LabelDataNotFoundException, ChapterContentNotFoundException) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label data {label_data_id} or its underlying revision text not found.",
        ) from e
    except LabelWordMismatchInvalidOperationException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Word mismatch detected: {str(e) or 'Label word does not match text.'}",
        ) from e
    except LabelExclusionViolationInvalidOperationException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Label overlap detected. Operations violate exclusion constraints.",
        ) from e
    except LabelOutOfBoundsInvalidOperationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Operation positions are out of bounds of the chapter text."
        ) from e
    except LabelNotExistsInvalidOperationException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="The label targeted for deletion does not exist."
        ) from e
    except LabelInvalidOperationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e) or "Invalid operation.") from e
    return


@router.post(
    "/label-groups/{labelGroupId}/label-datas/auto-labels",
    response_model=schemas.CreateLabelDataByAutoLabelStatus,
    responses={
        404: {"model": DetailHTTPErrorResponse, "description": "Label group not found."},
        409: {
            "model": RequestConflictErrorResponse,
            "description": "Request key conflict.",
        },
    },
)
@ttl_cache(ttl=60, cache=redis_cache, serialize_ret=serialize_response_model(schemas.CreateLabelDataByAutoLabelStatus))
def create_label_datas_by_auto_labels(
    label_group_id: Annotated[uuid.UUID, Path(alias="labelGroupId")],
    request: schemas.CreateLabelDataByAutoLabel,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request_key: Annotated[uuid.UUID | None, Query(alias="requestKey")] = None,
):
    """
    Creates label datas and populates labels from autolabel results.
    """
    result = insert_label_datas_by_autolabels(db, current_user, label_group_id, request)
    return result
