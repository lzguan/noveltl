import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.models import User, UserType
from ..database import get_db
from ..novels.exceptions import ChapterNotFoundException
from .schemas import EditChapterData
from .service import query_edit_chapter_data

router = APIRouter()


@router.get("/edit-chapter-data/{chapterId}", response_model=EditChapterData)
def read_edit_chapter_data(
    chapter_id: Annotated[uuid.UUID, Path(alias="chapterId")],
    novel_id: Annotated[uuid.UUID, Query(alias="novelId")],
    label_groups_num: Annotated[int, Query(alias="labelGroupsNum", ge=1, le=20)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    subject_id: Annotated[uuid.UUID | None, Query(alias="subjectId")] = None,
):
    """
    Gets all data associated with a chapter required for editing.

    Args:
        chapter_id: Chapter id of requested chapter
        novel_id: Novel id of requested chapter

    Raises:
        404: Chapter not found (or insufficient permissions).
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
            return query_edit_chapter_data(db, subject_user, chapter_id, novel_id, label_groups_num)
        return query_edit_chapter_data(db, current_user, chapter_id, novel_id, label_groups_num)
    except ChapterNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found or insufficient permissions."
        ) from e
