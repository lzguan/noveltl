import uuid
from collections.abc import Sequence
from typing import Annotated, Literal

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from pydantic import Field
from sqlalchemy import VARCHAR, Boolean, Integer, Text, column, insert, select, values
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from src.auth.models import User
from src.exceptions import InsufficientPermissionsException
from src.novels.constants import MAX_CHAPTER_TITLE_LEN
from src.novels.exceptions import ChapterNumDuplicateException, NovelNotFoundException
from src.novels.models import Chapter, ChapterContent
from src.novels.permissions import (
    chapter_mod_access_insert,
)
from src.schemas import Model


class ChapterUpload(Model):
    chapter_num: int
    chapter_title: str | None = Field(default=None, max_length=MAX_CHAPTER_TITLE_LEN)
    chapter_content_text: str
    chapter_is_public: bool = Field(default=False)


class BulkChapterUploadV1(Model):
    novel_id: uuid.UUID
    chapters: list[ChapterUpload] = Field(max_length=10000, min_length=1)
    version: Literal["v1"]


BulkChapterUpload = Annotated[BulkChapterUploadV1, Field(discriminator="version")]


def upload_v1(db: Session, current_user: User, request: BulkChapterUploadV1) -> Sequence[Chapter]:
    """
    Uploads multiple chapters to a novel in bulk.

    Args:
        db (Session): The database session.
        current_user (User): The currently authenticated user.
        request (BulkChapterUploadV1): The request object containing the novel ID and chapters to upload.

    Raises:
        NovelNotFoundException: If the specified novel does not exist or the user does not have permission to upload chapters to it.
        ChapterNumDuplicateException: If a chapter with the same number already exists for the novel.
        ValueError: If the chapter title is too long.
    """
    cols = (
        column("novel_id", postgresql.UUID),
        column("chapter_num", Integer),
        column("chapter_title", VARCHAR(MAX_CHAPTER_TITLE_LEN)),
        column("chapter_is_public", Boolean),
    )
    data = [
        (
            request.novel_id,
            u.chapter_num,
            u.chapter_title if u.chapter_title is not None else f"Chapter {u.chapter_num}",
            u.chapter_is_public,
        )
        for u in request.chapters
    ]
    vals = select(values(*cols).data(data).alias("vals"))
    vals = chapter_mod_access_insert(vals, current_user, request.novel_id)
    stmt = insert(Chapter).from_select(cols, vals).returning(Chapter)
    try:
        result = db.execute(stmt)
        result_scalars = result.scalars().all()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise NovelNotFoundException from e
            elif e.orig.pgcode == errorcodes.UNIQUE_VIOLATION:
                raise ChapterNumDuplicateException from e
        raise e
    except DataError as e:
        db.rollback()
        raise ValueError("Chapter title is too long") from e
    except Exception as e:
        db.rollback()
        raise e

    if len(result_scalars) != len(request.chapters):
        raise InsufficientPermissionsException("You do not have permission to upload chapters to this novel.")

    num_content_dict = {u.chapter_num: u.chapter_content_text for u in request.chapters}
    num_id_dict: dict[int, Chapter] = {chapter.chapter_num: chapter for chapter in result_scalars}

    cols2 = (
        column("chapter_id", postgresql.UUID),
        column("chapter_content_text", Text),
        column("chapter_content_version", Integer),
    )
    vals = select(
        values(*cols2)
        .data([(num_id_dict[num].chapter_id, num_content_dict[num], 1) for num in num_id_dict])
        .alias("vals2")
    )
    stmt2 = insert(ChapterContent).from_select(cols2, vals)

    try:
        db.execute(stmt2)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

    return result_scalars
