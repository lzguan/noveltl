"""
Service functions for novels/chapters.

Todo:
    Implement user permissions.
"""

import logging
import uuid
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, cast

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from sqlalchemy import CursorResult, and_, delete, exists, func, insert, literal, select, update
from sqlalchemy.exc import DataError, IntegrityError, NoResultFound
from sqlalchemy.orm import Session, aliased, defer

from ..auth.models import User
from ..exceptions import DataTooLongException, InsufficientPermissionsException
from ..labels import models as label_models
from ..labels import schemas as label_schemas
from ..languages.exceptions import LanguageNotFoundException
from ..schemas import OperationStatus
from . import models, schemas
from .constants import Role, Visibility
from .exceptions import (
    ChapterContentNotFoundException,
    ChapterContentOutdatedException,
    ChapterDeleteFailedException,
    ChapterNotFoundException,
    ChapterNumDuplicateException,
    NovelNotFoundException,
    SourceWorkNotFoundException,
)
from .permissions import (
    chapter_content_mod_access_insert,
    chapter_content_mod_access_select,
    chapter_mod_access_delete,
    chapter_mod_access_insert,
    chapter_mod_access_select,
    chapter_mod_access_update,
    novel_mod_access_select,
    novel_mod_access_update,
    source_work_mod_access_select,
    source_work_mod_access_update,
)
from .utils import apply_text_ops

logger = logging.getLogger(__name__)


def query_source_works_by_title(
    db: Session, current_user: User | None, source_work_title: str | None, ret_novels: bool
) -> Sequence[tuple[models.SourceWork, list[models.Novel]]]:
    """
    Queries source works with source_work_title as substring.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying. Can be None for guest access.
        source_work_title: Substring we wish to search for in source work titles.
        ret_novels: If True, return a list of tuples of (SourceWork, list of Novels with that SourceWork). Otherwise just return a list of SourceWorks and an empty list of Novels.
    """
    if source_work_title is None:
        search_term = "%"
    else:
        search_term = f"%{source_work_title}%"
    q = select(models.SourceWork).where(models.SourceWork.source_work_title.ilike(search_term))
    q = source_work_mod_access_select(q, current_user)
    result = db.execute(q)
    result_scalars = result.scalars().all()
    if ret_novels:
        source_work_ids = [sw.source_work_id for sw in result_scalars]
        novels_q = select(models.Novel).where(models.Novel.source_work_id.in_(source_work_ids))
        novels_q = novel_mod_access_select(novels_q, current_user)
        novels_result = db.execute(novels_q)
        novels_scalars = novels_result.scalars().all()
        novels_by_source_work = defaultdict(list)
        for novel in novels_scalars:
            novels_by_source_work[novel.source_work_id].append(novel)
        return [(sw, novels_by_source_work[sw.source_work_id]) for sw in result_scalars]

    return [(sw, []) for sw in result_scalars]


def query_source_work_by_id(db: Session, current_user: User | None, source_work_id: uuid.UUID) -> models.SourceWork:
    """
    Queries a source work by id.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying. Can be None for guest access.
        source_work_id: id of source work in database.

    Raises:
        SourceWorkNotFoundException: Source work not found in database.
    """
    q = select(models.SourceWork).where(models.SourceWork.source_work_id == source_work_id)
    q = source_work_mod_access_select(q, current_user)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise SourceWorkNotFoundException from e
    return result_scalar


def query_novels_by_source_work(
    db: Session, current_user: User | None, source_work_id: uuid.UUID
) -> Sequence[models.Novel]:
    """
    Queries novels with a specific source work.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying. Can be None for guest access.
        source_work_id: id of source work of novels we are querying.

    Raises:
        SourceWorkNotFoundException: Source work not found in database (or insufficient permissions to view it).
    """
    q = select(models.Novel).where(models.Novel.source_work_id == source_work_id)
    q = novel_mod_access_select(q, current_user)
    result = db.execute(q)
    result_scalars = result.scalars().all()
    if len(result_scalars) == 0:
        query_source_work_by_id(db, current_user, source_work_id)
    return result_scalars


def insert_source_work(db: Session, current_user: User, request: schemas.CreateSourceWork) -> models.SourceWork:
    """
    Insert a new source work into the database.

    Args:
        db: Database which we are inserting into.
        current_user: User performing the insert. Any authenticated user can create a source work.
        request: Metadata of source work.

    Raises:
        DataTooLongException: String is too long in some field of data we are inserting.
    """
    source_work = models.SourceWork(**request.model_dump())
    try:
        db.add(source_work)
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise
    except Exception:
        db.rollback()
        raise
    return source_work


def modify_source_work(
    db: Session, current_user: User, source_work_id: uuid.UUID, request: schemas.UpdateSourceWork
) -> models.SourceWork:
    """
    Modify a source work's metadata.

    Args:
        db: Database containing the source work to modify.
        current_user: User performing the modify. Must be admin or owner of a child novel.
        source_work_id: id of source work to modify.
        request: Proposed updated metadata.

    Raises:
        SourceWorkNotFoundException: Source work not found in database (or insufficient permissions).
        InsufficientPermissionsException: User does not have permission to modify this source work.
        DataTooLongException: Data we are updating to is too long for some string field.
    """
    stmt = (
        update(models.SourceWork)
        .where(models.SourceWork.source_work_id == source_work_id)
        .values(request.model_dump(exclude_unset=True))
    )
    stmt = source_work_mod_access_update(stmt, current_user)
    stmt = stmt.returning(models.SourceWork)
    try:
        result = db.execute(stmt)
        result_row = result.scalar_one()
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise
    except NoResultFound as e:
        db.rollback()
        query_source_work_by_id(db, current_user, source_work_id)
        raise InsufficientPermissionsException from e
    except Exception:
        db.rollback()
        raise
    return result_row


def query_novels_by_title(db: Session, current_user: User | None, novel_title: str | None) -> Sequence[models.Novel]:
    """
    Queries novels with novel_title as substring. Selects only public novels.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying. Can be None for guest access.
        novel_title: Substring we wish to search for.
    """
    if novel_title is None:
        search_term = "%"
    else:
        search_term = f"%{novel_title}%"
    q = (
        select(models.Novel)
        .where(models.Novel.novel_title.ilike(search_term))
        .where(models.Novel.novel_visibility == Visibility.PUBLIC)
    )
    result = db.execute(q)
    result_scalars = result.scalars().all()

    return result_scalars


def query_novels_by_current_user(
    db: Session, current_user: User, editable: bool, title_contains: str | None
) -> list[models.Novel]:
    """
    Queries all novels that the current user has special access to.

    Args:
        db: Database from which we are querying from.
        current_user: User that is querying.
        editable: If True, only select novels that the user can edit. Otherwise select all such novels.
    """
    subq = select(models.NovelContributor).where(
        and_(
            models.NovelContributor.novel_id == models.Novel.novel_id,
            models.NovelContributor.user_id == current_user.user_id,
        )
    )
    if editable:
        subq = subq.where(models.NovelContributor.contributor_role.in_([Role.EDITOR, Role.OWNER]))
    q = select(models.Novel).where(exists(subq))

    if title_contains:
        q = q.where(models.Novel.novel_title.ilike(f"%{title_contains}%"))

    result = db.execute(q)
    result_scalars = result.scalars().all()
    return list(result_scalars)


def query_novel_by_id(db: Session, current_user: User | None, novel_id: uuid.UUID) -> models.Novel:
    """
    Queries a novel by id. Will return a novel if the user has permission to view it and throws an exception otherwise.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying. Can be None for guest access.
        novel_id: id of novel in database.

    Raises:
        NovelNotFoundException: Novel not found in database (or insufficient permissions to view it).
    """
    q = select(models.Novel).where(models.Novel.novel_id == novel_id)
    q = novel_mod_access_select(q, current_user)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise NovelNotFoundException from e
    return result_scalar


def query_novel_and_users_by_id(db: Session, current_user: User, novel_id: uuid.UUID) -> schemas.NovelAndUsers:
    """
    Queries a novel and its contributors by id. Will return a novel if the user has permission to view it and throws an exception otherwise.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying. Can be None for guest access.
        novel_id: id of novel in database.
    """
    q = (
        select(models.Novel, models.User)
        .where(models.Novel.novel_id == novel_id)
        .join(models.NovelContributor, models.NovelContributor.novel_id == models.Novel.novel_id)
        .join(models.User, models.User.user_id == models.NovelContributor.user_id)
    )
    q = novel_mod_access_select(q, current_user)
    result = db.execute(q)
    rows = result.all()
    if len(rows) == 0:
        raise NovelNotFoundException
    novel = rows[0][0]
    users = [row[1] for row in rows]
    return schemas.NovelAndUsers(novel=novel, users=users)


def query_chapters_by_novel(
    db: Session, current_user: User | None, novel_id: uuid.UUID, start: int | None, end: int | None
) -> Sequence[models.Chapter]:
    """
    Query all chapters of a specific novel satisfying certain conditions. Only returns chapters that the user has permission to view.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying. Depending on permissions, will only be allowed to view public chapters. TBD
        novel_id: id of novel we are querying chapters from.
        start: If not none, then only query chapters with chapter_num >= start
        end: If not none, then only query chapters with chapter_num < end

    Raises:
        NovelNotFoundException: novel with corresponding novel_id is not in database (or insufficient permissions to view it).
    """
    q = (
        select(models.Chapter)
        .select_from(models.Novel)
        .where(models.Novel.novel_id == novel_id)
        .join(models.Chapter, models.Chapter.novel_id == models.Novel.novel_id)
    )
    if start is not None:
        q = q.where(models.Chapter.chapter_num >= start)
    if end is not None:
        q = q.where(models.Chapter.chapter_num < end)
    q = chapter_mod_access_select(q, current_user)
    q = q.order_by(models.Chapter.chapter_num.asc())
    result = db.execute(q)
    result_scalars = result.scalars().all()
    if len(result_scalars) == 0:
        query_novel_by_id(db, current_user, novel_id)
    return result_scalars


def query_chapter_by_id(db: Session, current_user: User | None, chapter_id: uuid.UUID) -> models.Chapter:
    """
    Query a chapter by id.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        chapter_id: id of chapter we are querying from.

    Raises:
        ChapterNotFoundException: Chapter not found in database (or insufficient permissions to view it).
    """
    q = (
        select(models.Chapter)
        .where(models.Chapter.chapter_id == chapter_id)
        .join(models.Novel, models.Chapter.novel_id == models.Novel.novel_id)
    )
    q = chapter_mod_access_select(q, current_user)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise ChapterNotFoundException from e
    return result_scalar


def query_chapter_content_by_most_recent(
    db: Session, current_user: User | None, chapter_id: uuid.UUID
) -> models.ChapterContent:
    """
    Query the most recent version of text of a specific chapter.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        chapter_id: ID of the chapter whose text we want to retrieve.

    Returns:
        The text of the specified chapter.

    Raises:
        ChapterContentNotFoundException: Content for the specified chapter is not found.
    """
    cc = aliased(models.ChapterContent)
    q = (
        select(models.ChapterContent)
        .where(models.ChapterContent.chapter_id == chapter_id)
        .where(
            models.ChapterContent.chapter_content_version
            == select(cc.chapter_content_version)
            .where(cc.chapter_id == chapter_id)
            .order_by(cc.chapter_content_version.desc())
            .limit(1)
            .scalar_subquery()
        )
    )
    try:
        q = chapter_content_mod_access_select(q, current_user)
        result = db.execute(q)
        result_row = result.scalar_one()
    except NoResultFound as e:
        query_chapter_by_id(db, current_user, chapter_id)
        raise ChapterContentNotFoundException from e
    return result_row


def query_chapter_content_by_id(
    db: Session, current_user: User | None, chapter_content_id: uuid.UUID
) -> models.ChapterContent:
    """
    Query a specific version of text of a specific chapter by the text's id.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        chapter_content_id: ID of the text we want to retrieve.

    Raises:
        ChapterContentNotFoundException: Text with corresponding ID is not found in database (or insufficient permissions to view it).
    """
    q = select(models.ChapterContent).where(models.ChapterContent.chapter_content_id == chapter_content_id)
    q = chapter_content_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        result_row = result.scalar_one()
    except NoResultFound as e:
        raise ChapterContentNotFoundException from e
    return result_row


def query_chapter_content_status(
    db: Session,
    current_user: User | None,
    chapter_id: uuid.UUID,
    chapter_content_id: uuid.UUID,
) -> OperationStatus:
    """
    Check whether a chapter_content_id is the latest version for its chapter.
    Queries the most recent chapter content version with read permissions applied,
    then compares against the provided chapter_content_id.

    Args:
        db: Database from which we are querying.
        current_user: User performing the check.
        chapter_id: ID of the chapter to check.
        chapter_content_id: ID of the chapter content to validate as current.

    Raises:
        ChapterContentNotFoundException: No chapter content found for chapter_content_id (or insufficient read permissions).
        ChapterContentOutdatedException: Chapter content exists but chapter_content_id is not the latest version.
    """
    q = (
        select(models.ChapterContent.chapter_content_id)
        .where(models.ChapterContent.chapter_id == chapter_id)
        .where(
            models.ChapterContent.chapter_content_version
            == select(func.max(models.ChapterContent.chapter_content_version))
            .where(models.ChapterContent.chapter_id == chapter_id)
            .scalar_subquery()
        )
    )
    q = chapter_content_mod_access_select(q, current_user)
    try:
        latest_id = db.execute(q).scalar_one()
    except NoResultFound as e:
        raise ChapterContentNotFoundException from e
    if latest_id != chapter_content_id:
        raise ChapterContentOutdatedException("Chapter content is outdated. Please refresh and try again.")
    return OperationStatus(status="success", detail="Chapter content is current.")


def query_chapter_content_ids_by_chapter_id(
    db: Session, current_user: User, chapter_id: uuid.UUID
) -> list[schemas.ChapterContentMeta]:
    """
    Query all text ids of a specific chapter.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        chapter_id: ID of the chapter whose text ids we want to retrieve.
    """
    q = (
        select(models.ChapterContent)
        .options(defer(models.ChapterContent.chapter_content_text))
        .where(models.ChapterContent.chapter_id == chapter_id)
    )
    q = chapter_content_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()
    return [schemas.ChapterContentMeta.model_validate(row) for row in result_rows]


def insert_novel(db: Session, current_user: User, request: schemas.CreateNovel) -> models.Novel:
    """
    Insert a novel into the database. If source_work_id is None, a new SourceWork
    is auto-created using the novel's title.

    Args:
        db: Database which we are inserting into.
        current_user: User performing the insert. Only users/admins can create novels.
        request: Metadata of novel.

    Raises:
        SourceWorkNotFoundException: Provided source_work_id does not exist.
        LanguageNotFoundException: Language code in request does not exist.
        DataTooLongException: String is too long in some field of data we are inserting.
    """
    try:
        if request.source_work_id is None:
            source_work = models.SourceWork(source_work_title=request.novel_title)
            db.add(source_work)
            db.flush()
            source_work_id = source_work.source_work_id
        else:
            source_work_id = request.source_work_id

        novel_data = request.model_dump(exclude={"source_work_id"})
        novel = models.Novel(**novel_data, source_work_id=source_work_id)
        db.add(novel)
        db.flush()
        contributor = models.NovelContributor(
            contributor_role=Role.OWNER, novel_id=novel.novel_id, user_id=current_user.user_id
        )
        db.add(contributor)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                constraint = getattr(e.orig.diag, "constraint_name", "") or ""
                if "source_work" in constraint:
                    raise SourceWorkNotFoundException from e
                raise LanguageNotFoundException from e
        raise
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise
    except Exception:
        db.rollback()
        raise
    return novel


def modify_novel(db: Session, current_user: User, novel_id: uuid.UUID, request: schemas.UpdateNovel) -> models.Novel:
    """
    Modifies novel with novel_id.

    Args:
        db: Database containing the novel to modify.
        current_user: User performing the modify. Exact user validation protocol has yet to be determined.
        novel_id: id of novel to modify.
        request: Proposed updated metadata.

    Raises:
        NovelNotFoundException: Novel not found in database (or insufficient permissions to view it).
        InsufficientPermissionsException: User does not have permission to modify this novel.
        DataTooLongException: Data we are updating to is too long for some string field.
    """
    stmt = update(models.Novel).where(models.Novel.novel_id == novel_id).values(request.model_dump(exclude_unset=True))
    stmt = novel_mod_access_update(stmt, current_user)
    stmt = stmt.returning(models.Novel)
    try:
        result = db.execute(stmt)
        result_row = result.scalar_one()
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise
    except NoResultFound as e:
        db.rollback()
        query_novel_by_id(db, current_user, novel_id)
        raise InsufficientPermissionsException from e
    except Exception:
        db.rollback()
        raise

    return result_row


def insert_chapter(
    db: Session, current_user: User, novel_id: uuid.UUID, request: schemas.CreateChapter
) -> tuple[models.Chapter, models.ChapterContent]:
    """
    Insert a chapter into a database with an initial empty ChapterContent (version 1).

    Args:
        db: Database into which we are inserting the chapter.
        current_user: User performing the insert.
        novel_id: id of novel the chapter belongs to
        request: Data to insert.

    Returns:
        Tuple of the new Chapter and its initial ChapterContent.

    Raises:
        NovelNotFoundException: Novel with novel_id does not exist in database (or insufficient permissions to view it).
        InsufficientPermissionsException: User does not have permission to insert a chapter for this novel.
        ChapterNumDuplicateException: Chapter with chapter_num already exists in db.
    """
    data = list(request.model_dump().items())
    data.append(("novel_id", novel_id))
    cols = [k for k, _ in data]

    vals = select(*[literal(v) for _, v in data])
    vals = chapter_mod_access_insert(vals, current_user, novel_id)
    stmt = insert(models.Chapter).from_select(cols, vals).returning(models.Chapter)

    try:
        result = db.execute(stmt)
        chapter = result.scalar_one()
        cc_vals = select(literal(chapter.chapter_id), literal(""), literal(1))
        cc_vals = chapter_content_mod_access_insert(cc_vals, current_user, chapter.chapter_id)
        cc_cols = ["chapter_id", "chapter_content_text", "chapter_content_version"]
        cc_stmt = insert(models.ChapterContent).from_select(cc_cols, cc_vals).returning(models.ChapterContent)
        chapter_content = db.execute(cc_stmt).scalar_one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise NovelNotFoundException from e
            if pgcode == errorcodes.UNIQUE_VIOLATION:
                raise ChapterNumDuplicateException from e
        raise
    except NoResultFound as e:
        db.rollback()
        query_novel_by_id(db, current_user, novel_id)
        raise InsufficientPermissionsException from e
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise
    except Exception:
        db.rollback()
        raise
    return chapter, chapter_content


def modify_chapter(
    db: Session,
    current_user: User,
    chapter_id: uuid.UUID,
    request: schemas.UpdateChapter,
) -> models.Chapter:
    """
    Modifies data of chapter with chapter_id.

    Args:
        db: Database that contains the chapter to modify.
        current_user: User performing the update.
        chapter_id: id of chapter we are modifying.

    Raises:
        ChapterNotFoundException: chapter_id does not correspond to a chapter in db (or insufficient permissions to view it).
        InsufficientPermissionsException: User does not have permission to modify this chapter.
        DataTooLongException: String we are trying to modify is too long.
    """
    stmt = (
        update(models.Chapter)
        .where(models.Chapter.chapter_id == chapter_id)
        .values(request.model_dump(exclude_unset=True))
    )
    stmt = chapter_mod_access_update(stmt, current_user)
    stmt = stmt.returning(models.Chapter)
    try:
        result = db.execute(stmt)
        chapter = result.scalar_one()
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise
    except NoResultFound as e:
        db.rollback()
        query_chapter_by_id(db, current_user, chapter_id)
        raise InsufficientPermissionsException from e
    except Exception:
        db.rollback()
        raise
    return chapter


def make_public_chapter(db: Session, current_user: User, chapter_id: uuid.UUID) -> models.Chapter:
    """
    Make a chapter public.

    Args:
        db: Database in which the data resides.
        current_user: User publishing the chapter.
        chapter_id: id of the chapter we are publishing.

    Raises:
        ChapterNotFoundException: Chapter with chapter_id not found (or insufficient permissions to view it).
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
    """
    stmt = update(models.Chapter).where(models.Chapter.chapter_id == chapter_id).values(chapter_is_public=True)
    stmt = chapter_mod_access_update(stmt, current_user)
    stmt = stmt.returning(models.Chapter)
    try:
        result = db.execute(stmt)
        chapter = result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        query_chapter_by_id(db, current_user, chapter_id)
        raise InsufficientPermissionsException from e
    except Exception:
        db.rollback()
        raise
    return chapter


def modify_chapter_content(
    db: Session,
    current_user: User,
    chapter_id: uuid.UUID,
    chapter_content_id: uuid.UUID,
    ops: list[schemas.TextOp],
) -> schemas.ModifyChapterContentResponse:
    """
    Modify the text of a chapter and port all label datas over, including those the current user does not have access to.

    Args:
        db: Database in which the data resides.
        current_user: User performing the update.
        chapter_id: id of the chapter we are modifying.
        chapter_content_id: id of the content we are modifying.
        ops: List of text operations to apply.

    Raises:
        ChapterContentNotFoundException: Chapter content with chapter_content_id not found (or insufficient permissions to view it).
        ChapterContentOutdatedException: Chapter content is outdated.
    """
    q = (
        select(models.ChapterContent)
        .where(models.ChapterContent.chapter_id == chapter_id)
        .where(
            models.ChapterContent.chapter_content_version
            == select(func.max(models.ChapterContent.chapter_content_version))
            .where(models.ChapterContent.chapter_id == chapter_id)
            .scalar_subquery()
        )
    )
    q = chapter_content_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        chapter_content = result.scalar_one()
    except NoResultFound as e:
        raise ChapterContentNotFoundException from e
    if chapter_content.chapter_content_id != chapter_content_id:
        raise ChapterContentOutdatedException("Chapter content is outdated. Please refresh and try again.")

    text = chapter_content.chapter_content_text

    q = (
        select(label_models.Label)
        .join(label_models.LabelData, label_models.Label.label_data_id == label_models.LabelData.label_data_id)
        .where(label_models.LabelData.chapter_content_id == chapter_content.chapter_content_id)
    )
    label_result = db.execute(q).scalars().all()

    labels = [label_schemas.Label.model_validate(label) for label in label_result]

    new_content, new_labels = apply_text_ops(text, ops, labels)

    vals = select(
        literal(chapter_content.chapter_id), literal(new_content), literal(chapter_content.chapter_content_version + 1)
    )
    cols = ["chapter_id", "chapter_content_text", "chapter_content_version"]
    vals = chapter_content_mod_access_insert(vals, current_user, chapter_content.chapter_id)
    stmt = (
        insert(models.ChapterContent)
        .from_select(cols, vals)
        .returning(models.ChapterContent.chapter_content_id, models.ChapterContent.chapter_content_version)
    )

    try:
        result = db.execute(stmt)
        new_chapter_content_id, new_chapter_content_version = result.one()
    except NoResultFound as e:
        db.rollback()
        # Distinguish between outdated text and insufficient write permissions.
        # query_chapter_content_status raises the appropriate exception.
        query_chapter_content_status(db, current_user, chapter_id, chapter_content_id)
        # If status check passes (shouldn't happen), raise generic error.
        raise InsufficientPermissionsException from e
    except Exception:
        db.rollback()
        raise

    qq = select(label_models.LabelData.label_data_id).where(
        label_models.LabelData.chapter_content_id == chapter_content.chapter_content_id
    )
    all_label_data_ids = db.execute(qq).scalars().all()
    # port label datas
    label_data_map: dict[uuid.UUID, list[label_schemas.Label]] = defaultdict(list)

    for ldid in all_label_data_ids:
        label_data_map[ldid] = []

    label_data_id_map: dict[uuid.UUID, uuid.UUID] = {}

    for label in new_labels:
        label_data_map[label.label_data_id].append(label)

    for label_data_id, labels in label_data_map.items():
        label_data_q = select(label_models.LabelData.label_group_id).where(
            label_models.LabelData.label_data_id == label_data_id
        )
        label_group_id = db.execute(label_data_q).scalar_one()
        stmt = (
            insert(label_models.LabelData)
            .values(label_group_id=label_group_id, chapter_content_id=new_chapter_content_id)
            .returning(label_models.LabelData)
        )
        label_data = db.execute(stmt).scalar_one()
        label_data_id_map[label_data_id] = label_data.label_data_id
        label_vals = [label.model_dump(exclude={"label_id"}) for label in labels]
        for label in label_vals:
            label["label_data_id"] = label_data.label_data_id
        if len(label_vals) > 0:
            stmt = insert(label_models.Label).values(label_vals)
            db.execute(stmt)
        else:
            logger.debug(
                f"No labels to port for label_data_id {label_data_id} and chapter_content_id {chapter_content.chapter_content_id}"
            )

    db.commit()

    return schemas.ModifyChapterContentResponse(
        chapter_content_id=new_chapter_content_id,
        chapter_content_version=new_chapter_content_version,
        label_data_id_map=label_data_id_map,
    )


def remove_chapter(db: Session, current_user: User, chapter_id: uuid.UUID) -> OperationStatus:
    """
    Remove a chapter from the database.

    Args:
        db: Database to remove from.
        current_user: User removing the chapter.
        chapter_id: id of chapter to remove.

    Raises:
        ChapterNotFoundException: Chapter with chapter_id not found (or insufficient permissions to view it).
        InsufficientPermissionsException: Current user has insufficient permissions to delete this chapter.
        ChapterDeleteFailedException: Delete failed for other reasons.
    """
    stmt = delete(models.Chapter).where(models.Chapter.chapter_id == chapter_id)
    stmt = chapter_mod_access_delete(stmt, current_user)
    try:
        result = db.execute(stmt)
        cursor_res = cast(CursorResult[Any], result)
        if cursor_res.rowcount == 0:
            db.rollback()
            query_chapter_by_id(db, current_user, chapter_id)
            raise InsufficientPermissionsException
        db.commit()
    except InsufficientPermissionsException as e:
        raise e
    except ChapterNotFoundException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise ChapterDeleteFailedException from e
    return OperationStatus(status="success", detail="Delete succeeded.")
