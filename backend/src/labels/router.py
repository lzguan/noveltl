from ..database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from .dependencies import *
from ..auth.dependencies import get_current_user
from .service import *
from .schemas import *
from typing import Annotated

router = APIRouter()

@router.get('/label-groups', response_model=List[schemas.LabelGroup])
def read_label_groups(
        novel_id : int,
        db: Annotated[Session, Depends(get_db)],
        current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Gets all label groups of the current user

    Args:
        db: Database dependency.
        current_user: Current user dependency.
        novel_id: id of novel to query label groups for.
    """
    return query_label_groups(db, current_user, novel_id)

@router.get('/label-groups/{label_group_id}', response_model=schemas.LabelGroup)
def read_label_group(
        label_group_id : int,
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[User, Depends(get_current_user)]
    ):
    try:
        label_group = query_label_group_by_id(db, current_user, label_group_id)
    except LabelGroupNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label group with id {label_group_id} not found."
        )
    return label_group

@router.get('/label-datas', response_model=List[schemas.LabelData])
def read_label_datas_by_group_chapters(
        label_group_id : int, 
        db : Annotated[Session, Depends(get_db)], 
        current_user : Annotated[User, Depends(get_current_user)],
        start : int | None = None,
        end : int | None = None
    ):
    label_datas = query_label_datas(db, current_user, label_group_id, start, end)

    return label_datas

@router.get('/label-datas/{label_data_id}', response_model=schemas.LabelData)
def read_label_data(
        label_data_id : int,
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[User, Depends(get_current_user)]
    ):
    try:
        label_data = query_label_data_by_id(db, current_user, label_data_id)
    except LabelDataNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label data not found."
        )
    return label_data

@router.get('/label-datas/{label_data_id}/labels', response_model=List[schemas.Label])
def read_labels_by_label_data(
        label_data_id : int,
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Get the specific list of labels inside a label data entry.
    """
    labels = query_labels_by_label_data_id(db, current_user, label_data_id)
    return labels

@router.post('/label-groups', response_model=schemas.LabelGroup)
def create_label_group(
        request: schemas.CreateLabelGroup,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
    ):
    """
    Creates a new label group.
    """
    try:
        label_group = insert_label_group(db, current_user, request)
    except NovelNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Novel associated with this label group not found."
        )
    except DataTooLongException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label group name is too long."
        )
    return label_group

@router.patch('/label-groups/{label_group_id}', response_model=schemas.LabelGroup)
def update_label_group(
        label_group_id: int,
        request: schemas.UpdateLabelGroup,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
    ):
    """
    Updates a label group (e.g. rename).
    """
    try:
        label_group = modify_label_group(db, current_user, label_group_id, request)
    except LabelGroupNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label group with id {label_group_id} not found."
        )
    except DataTooLongException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label group name is too long."
        )
    return label_group

@router.post('/label-groups/{label_group_id}/label-datas', response_model=schemas.LabelData)
def create_label_data(
        label_group_id: int,
        request: schemas.CreateLabelData,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
    ):
    """
    Creates a label data entry. 
    Requires the chapter revision to be Final.
    """
    try:
        label_data = insert_label_data(db, current_user, label_group_id, request)
    except LabelGroupNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label group not found."
        )
    except RawChapterRevisionNotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Raw chapter revision not found."
        )
    except LabelDataRevisionDuplicateException:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Label data for this chapter already exists in this group."
        )
    except NotFoundException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label group or raw chapter revision not found."
        )
    return label_data

@router.patch('/label-datas/{label_data_id}', status_code=status.HTTP_204_NO_CONTENT)
def update_label_data_stream(
        label_data_id: int,
        request: schemas.UpdateLabelDataStream,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)]
    ):
    """
    Applies a stream of edit operations to labels.
    """
    try:
        modify_label_data_by_stream(db, current_user, label_data_id, request)
    except (LabelDataNotFoundException, RawChapterRevisionNotFoundException):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Label Data {label_data_id} or its underlying Chapter Revision not found."
        )
    except LabelWordMismatchInvalidOperationException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Word mismatch detected: {str(e) or 'Label word does not match text.'}"
        )
    except LabelExclusionViolationInvalidOperationException:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Label overlap detected. Operations violate exclusion constraints."
        )
    except LabelOutOfBoundsInvalidOperationException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operation positions are out of bounds of the chapter text."
        )
    except LabelNotExistsInvalidOperationException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The label targeted for deletion does not exist."
        )
    except LabelInvalidOperationException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) or "Invalid operation."
        )

    return

@router.post(
    '/label-groups/{label_group_id}/label-datas/auto-labels', 
    response_model=schemas.CreateLabelDataByAutoLabelStatus
)
def create_label_datas_by_auto_labels(
        label_group_id : int, 
        request : schemas.CreateLabelDataByAutoLabel,
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Creates label datas and populates its labels using the request to filter which label datas to use.

    Args:
        label_group_id: id for label group we are populating.
        request: Request for things to filter on.
        db: Database dependency.
        current_user: Current user dependency.
    """
    result = insert_label_datas_by_autolabels(db, current_user, label_group_id, request)
    return result