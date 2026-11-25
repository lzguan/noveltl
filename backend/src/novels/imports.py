import uuid
from collections.abc import Sequence

import psycopg
from psycopg.errors import DataError as PsycopgDataError
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from pydantic import Field
from sqlalchemy import DateTime, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.exceptions import InsufficientPermissionsException
from src.novels.constants import MAX_CHAPTER_TITLE_LEN
from src.novels.exceptions import ChapterNumDuplicateException, NovelNotFoundException
from src.novels.models import Chapter
from src.novels.permissions import chapter_mod_access_insert
from src.schemas import Model

_COPY_CHAPTERS_SQL = (
    "COPY chapters (chapter_id, novel_id, chapter_num, chapter_title, chapter_is_public, created_at, updated_at) "
    "FROM STDIN (FORMAT BINARY)"
)
_COPY_CHAPTERS_TYPES = ["uuid", "uuid", "int4", "varchar", "bool", "timestamp", "timestamp"]

_COPY_CONTENTS_SQL = (
    "COPY chapter_contents (chapter_id, chapter_content_text, chapter_content_version, created_at, updated_at) "
    "FROM STDIN (FORMAT BINARY)"
)
_COPY_CONTENTS_TYPES = ["uuid", "text", "int4", "timestamp", "timestamp"]


class ChapterUpload(Model):
    chapter_num: int
    chapter_title: str | None = Field(default=None, max_length=MAX_CHAPTER_TITLE_LEN)
    chapter_content_text: str
    chapter_is_public: bool = Field(default=False)


class BulkChapterUploadV1(Model):
    chapters: list[ChapterUpload] = Field(max_length=10000, min_length=1)


async def upload_v1(
    db: AsyncSession, current_user: User, novel_id: uuid.UUID, request: BulkChapterUploadV1
) -> Sequence[Chapter]:
    """
    Uploads multiple chapters to a novel in bulk.

    Args:
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
        novel_id (uuid.UUID): The ID of the novel to which chapters are being uploaded.
        request (BulkChapterUploadV1): The request object containing the novel ID and chapters to upload.

    Raises:
        NovelNotFoundException: If the specified novel does not exist or the user does not have permission to upload chapters to it.
        ChapterNumDuplicateException: If a chapter with the same number already exists for the novel.
        ValueError: If the chapter title is too long.
    """
    permission_q = chapter_mod_access_insert(select(cast(func.now(), DateTime)), current_user, novel_id)
    now = (await db.execute(permission_q)).scalar_one_or_none()
    if now is None:
        await db.rollback()
        raise InsufficientPermissionsException("You do not have permission to upload chapters to this novel.")

    inserted_chapters = [
        Chapter(
            chapter_id=uuid.uuid4(),
            novel_id=novel_id,
            chapter_num=u.chapter_num,
            chapter_title=u.chapter_title if u.chapter_title is not None else f"Chapter {u.chapter_num}",
            chapter_is_public=u.chapter_is_public,
        )
        for u in request.chapters
    ]

    try:
        conn = await db.connection()
        raw_conn = await conn.get_raw_connection()
        driver_conn = raw_conn.driver_connection
        if not isinstance(driver_conn, psycopg.AsyncConnection):
            raise TypeError(f"Expected psycopg AsyncConnection, got {type(driver_conn)!r}")

        async with driver_conn.cursor() as cur:
            async with cur.copy(_COPY_CHAPTERS_SQL) as copy:
                copy.set_types(_COPY_CHAPTERS_TYPES)
                for chapter in inserted_chapters:
                    await copy.write_row(
                        (
                            chapter.chapter_id,
                            novel_id,
                            chapter.chapter_num,
                            chapter.chapter_title,
                            chapter.chapter_is_public,
                            now,
                            now,
                        )
                    )
            async with cur.copy(_COPY_CONTENTS_SQL) as copy:
                copy.set_types(_COPY_CONTENTS_TYPES)
                for chapter, upload in zip(inserted_chapters, request.chapters, strict=True):
                    await copy.write_row((chapter.chapter_id, upload.chapter_content_text, 1, now, now))

        await db.commit()
    except ForeignKeyViolation as e:
        await db.rollback()
        raise NovelNotFoundException from e
    except UniqueViolation as e:
        await db.rollback()
        raise ChapterNumDuplicateException from e
    except PsycopgDataError as e:
        await db.rollback()
        raise ValueError("Chapter title is too long") from e
    except Exception:
        await db.rollback()
        raise

    return inserted_chapters
