import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.novels.exceptions import ChapterContentNotFoundException

from ..auth.dependencies import get_current_user
from ..auth.models import User, UserType
from ..database import get_db
from .schemas import EagerEntry, EditChapterData
from .service import query_edit_chapter_data, query_edit_chapter_data_only_label_data

router = APIRouter()


@router.post("/edit-chapter-data/{chapterId}", response_model=EditChapterData)
def read_edit_chapter_data(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    eager: Annotated[
        list[uuid.UUID],
        Body(alias="eager", description="List of label group IDs for which to fetch eager label data"),
    ],
    subject_id: Annotated[uuid.UUID | None, Query(alias="subjectId")] = None,
):
    """
    Gets all data associated with a chapter required for editing.

    Args:
        chapter_id: Chapter id of requested chapter
        eager: List of label group IDs for which to fetch eager label data

    Raises:
        404: Chapter not found (or insufficient permissions).
        403: Insufficient permissions to access data for other user.
    """
    try:
        if subject_id is not None and subject_id != current_user.user_id and current_user.user_type != UserType.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to access data for other user."
            )
        elif subject_id is not None and subject_id != current_user.user_id:
            q = select(User).where(User.user_id == subject_id)
            subject_user = db.execute(q).scalar_one_or_none()
            if subject_user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject user not found.")
            return query_edit_chapter_data(db, subject_user, chapter_id, eager)
        return query_edit_chapter_data(db, current_user, chapter_id, eager)
    except ChapterContentNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found or insufficient permissions."
        ) from e


@router.post("/edit-chapter-data/{chapterId}/label-data", response_model=list[EagerEntry])
def read_edit_chapter_label_data(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    label_group_ids: Annotated[
        list[uuid.UUID],
        Body(alias="labelGroupIds", description="Label group IDs to fetch label data and labels for"),
    ],
    subject_id: Annotated[uuid.UUID | None, Query(alias="subjectId")] = None,
):
    """
    Fetch label data and labels for specific label groups on a chapter's most
    recent content version. Used by the reload group operation.

    Raises:
        404: Chapter not found (or insufficient permissions).
        403: Insufficient permissions to access data for other user.
    """
    try:
        if subject_id is not None and subject_id != current_user.user_id and current_user.user_type != UserType.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to access data for other user."
            )
        elif subject_id is not None and subject_id != current_user.user_id:
            q = select(User).where(User.user_id == subject_id)
            subject_user = db.execute(q).scalar_one_or_none()
            if subject_user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject user not found.")
            return query_edit_chapter_data_only_label_data(db, subject_user, chapter_id, label_group_ids)
        return query_edit_chapter_data_only_label_data(db, current_user, chapter_id, label_group_ids)
    except ChapterContentNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found or insufficient permissions."
        ) from e
