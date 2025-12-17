from ..database import get_db
from fastapi import APIRouter, Depends, HTTPException, status, Query
from ..auth.dependencies import get_current_user
from .service import *
from . import schemas
from typing import Annotated, Dict
from ..redis import get_redis
from .utils import *

router = APIRouter()

@router.get(
    '/auto-labels/{auto_label_id}', 
    response_model=schemas.AutoLabel
)
async def read_autolabel_by_id(
        auto_label_id : int, 
        db : Annotated[Session, Depends(get_db)], 
        current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Endpoint for retrieving autolabel from database.

    Args:
        auto_label_id: Integer id for auto label.
        db: Database dependency.
        current_user: Current user dependency. 
    """
    try:
        autolabel = query_auto_label_by_id(db, current_user, auto_label_id)
    except AutoLabelNotFoundException:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No autolabel with id {auto_label_id} found."
        )
    except InsufficientPermissionsException:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view this resource."
        )
    return autolabel

@router.get('/auto-labels', response_model=Dict[int, schemas.AutoLabelMeta])
async def read_autolabels(
        novel_id : int, 
        db : Annotated[Session, Depends(get_db)], 
        current_user : Annotated[User, Depends(get_current_user)], 
        raw_chapter_ids : Annotated[List[int] | None, Query()] = None, 
        raw_chapter_revision_ids : Annotated[List[int] | None, Query()] = None,  
        start : int | None = None, 
        end : int | None = None, 
        model_names : Annotated[List[str] | None, Query()] = None,
    ):
    auto_labels = query_auto_labels(db, current_user, novel_id, raw_chapter_ids, raw_chapter_revision_ids, start, end, model_names)
    return auto_labels

@router.post(
    '/auto-labels', 
    response_model=schemas.CreateAutoLabelsStatus
)
async def create_autolabels(
        request : schemas.CreateAutoLabels, 
        db : Annotated[Session, Depends(get_db)], 
        current_user : Annotated[User, Depends(get_current_user)]
    ):
    redis = get_redis()
    if redis is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Request queueing down."
        )
    dispatcher = ArqDispatcher(redis)
    try:
        insert_status = await insert_auto_labels(db, current_user, dispatcher, request)
    except AutoLabelDuplicateException:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="An unexpected error occurred, likely because you tried creating auto labels at the same time as someone else."
        )
    return insert_status