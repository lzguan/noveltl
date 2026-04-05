import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.models import User
from ..database import get_db
from . import schemas
from .dependencies import get_arq_dispatcher
from .exceptions import AutoLabelDuplicateException, AutoLabelNotFoundException
from .service import insert_auto_labels, query_auto_label_by_id, query_auto_labels
from .utils import AutoLabelDispatcher

router = APIRouter()

@router.get(
    '/auto-labels/{auto_label_id}',
    response_model=schemas.AutoLabel
)
async def read_autolabel_by_id(
        auto_label_id : uuid.UUID,
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[User, Depends(get_current_user)]
    ):
    """
    Endpoint for retrieving autolabel from database.

    Args:
        auto_label_id: UUID for auto label.
        db: Database dependency.
        current_user: Current user dependency.
    """
    try:
        autolabel = query_auto_label_by_id(db, current_user, auto_label_id)
    except AutoLabelNotFoundException as e:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No autolabel with id {auto_label_id} found."
        ) from e
    return autolabel

@router.get('/auto-labels', response_model=list[schemas.AutoLabelMeta])
async def read_autolabels(
        novel_id : Annotated[uuid.UUID, Query(alias="novel-id")],
        db : Annotated[Session, Depends(get_db)],
        current_user : Annotated[User, Depends(get_current_user)],
        chapter_ids : Annotated[list[uuid.UUID] | None, Query(alias="chapter-ids")] = None,
        start : int | None = None,
        end : int | None = None,
        model_names : Annotated[list[str] | None, Query(alias="model-names")] = None,
    ):
    auto_labels = query_auto_labels(db, current_user, novel_id, chapter_ids, start, end, model_names)
    return auto_labels

@router.post(
    '/auto-labels',
    response_model=list[schemas.AutoLabelMeta]
)
async def create_autolabels(
        request : schemas.CreateAutoLabels,
        db : Annotated[Session, Depends(get_db)],
        dispatcher : Annotated[AutoLabelDispatcher, Depends(get_arq_dispatcher)],
        current_user : Annotated[User, Depends(get_current_user)]
    ):
    try:
        insert_status = await insert_auto_labels(db, current_user, dispatcher, request)
    except AutoLabelDuplicateException as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="An unexpected error occurred, likely because you tried creating auto labels at the same time as someone else."
        ) from e
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unknown error occured: {str(e)}"
        ) from e
    return insert_status
