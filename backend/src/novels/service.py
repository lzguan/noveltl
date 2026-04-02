"""
Service functions for novels/chapters.

Todo:
    Implement user permissions.
"""

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
from ..exceptions import DataTooLongException, InsufficientPermissionsException, UnknownError
from ..labels import models as label_models
from ..labels import schemas as label_schemas
from ..languages.exceptions import LanguageNotFoundException
from ..schemas import OperationStatus
from . import models, schemas
from .constants import Role, Visibility
from .exceptions import (
    ChapterNotFoundException,
    ChapterNumDuplicateException,
    DeleteRevisionFailedException,
    DuplicateNovelAssociationException,
    NovelAssociationNotFoundException,
    NovelNotFoundException,
    RevisionMakePrimaryFailedException,
    RevisionNotFoundException,
    RevisionNotPublicException,
    RevisionTextNotFoundException,
    RevisionTextOutdatedException,
)
from .permissions import (
    chapter_mod_access_insert,
    chapter_mod_access_select,
    novel_mod_access_select,
    novel_mod_access_update,
    revision_mod_access_delete,
    revision_mod_access_insert,
    revision_mod_access_select,
    revision_mod_access_update,
    revision_text_mod_access_insert,
    revision_text_mod_access_select,
)
from .utils import apply_text_ops


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
    subq = select(models.Contributor).where(
        and_(models.Contributor.novel_id == models.Novel.novel_id, models.Contributor.user_id == current_user.user_id)
    )
    if editable:
        subq = subq.where(models.Contributor.contributor_role.in_([Role.EDITOR, Role.OWNER]))
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


def query_revision_by_id(db: Session, current_user: User | None, revision_id: uuid.UUID) -> models.Revision:
    """
    Query a chapter revision by id.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        revision_id: id of chapter revision we are querying.

    Raises:
        RevisionNotFoundException: Chapter revision not found in database (or insufficient permissions to view it).
    """
    q = (
        select(models.Revision)
        .where(models.Revision.revision_id == revision_id)
        .join(models.Chapter, models.Chapter.chapter_id == models.Revision.chapter_id)
        .join(models.Novel, models.Novel.novel_id == models.Chapter.novel_id)
    )
    q = revision_mod_access_select(q, current_user)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise RevisionNotFoundException from e
    return result_scalar


def query_revisions_by_chapter(
    db: Session, current_user: User | None, chapter_id: uuid.UUID, is_public: bool | None, is_primary: bool | None
) -> list[models.Revision]:
    """
    Query all chapter revisions from a chapter_id satisfying certain requirements.

    Args:
        db: Database from which we are querying.
        current_user: User performing the query.
        chapter_id: id of chapter we are querying from.
        is_public: If not None, only select public chapters.
        is_primary: If not None, only select primary chapters.

    Raises:
        ChapterNotFoundException: Chapter with corresponding chapter_id is not in database (or no permissions to view it).
    Notes:
        The caller should be responsible for converting to the best pydantic model for the use case.
    """
    q = (
        select(models.Revision)
        .where(models.Revision.chapter_id == chapter_id)
        .join(models.Chapter, models.Chapter.chapter_id == models.Revision.chapter_id)
        .join(models.Novel, models.Novel.novel_id == models.Chapter.novel_id)
        .order_by(
            models.Revision.revision_is_primary.desc(),
            models.Revision.revision_is_public.desc(),
            models.Revision.updated_at.desc(),
        )
    )
    if is_public is not None:
        q = q.where(models.Revision.revision_is_public == is_public)
    if is_primary is not None:
        q = q.where(models.Revision.revision_is_primary == is_primary)
    q = revision_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()
    if len(result_rows) == 0:
        query_chapter_by_id(db, current_user, chapter_id)
    return list(result_rows)


def query_revisions_by_novel(
    db: Session,
    current_user: User | None,
    novel_id: uuid.UUID,
    start: int | None,
    end: int | None,
    is_public: bool | None,
    is_primary: bool | None,
) -> list[models.Revision]:
    """
    Query all chapter revisions from novel novel_id satisfying certain restrictions. Returns a dictionary in the format
        `chapter_num : List[RevisionMeta]`

    Args:
        db: Database from which we are querying from.
        current_user: User that is querying.
        novel_id: id of novel we are querying chapter revisions from.
        start: If not None, then only query chapter revisions that have chapter_num >= start.
        end: If not None, then only query chapter revisions that have chapter_num < end.
        is_public: If not None, then filter novels by public status.
        is_primary: If not None, then filter novels by primary status.

    Raises:
        NovelNotFoundException: novel with corresponding novel_id is not in database (or insufficient permissions to view it).
    """
    q = (
        select(models.Revision)
        .join(models.Chapter, models.Chapter.chapter_id == models.Revision.chapter_id)
        .join(models.Novel, models.Novel.novel_id == models.Chapter.novel_id)
        .where(models.Novel.novel_id == novel_id)
        .order_by(
            models.Chapter.chapter_num.asc(),
            models.Revision.revision_is_primary.desc(),
            models.Revision.revision_is_public.desc(),
            models.Revision.updated_at.desc(),
        )
    )
    if start is not None:
        q = q.where(models.Chapter.chapter_num >= start)
    if end is not None:
        q = q.where(models.Chapter.chapter_num < end)
    if is_public is not None:
        q = q.where(models.Revision.revision_is_public == is_public)
    if is_primary is not None:
        q = q.where(models.Revision.revision_is_primary == is_primary)
    q = revision_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()
    if len(result_rows) == 0:
        query_novel_by_id(db, current_user, novel_id)
    return list(result_rows)


def query_revision_text_by_most_recent(
    db: Session, current_user: User | None, revision_id: uuid.UUID
) -> models.RevisionText:
    """
    Query the most recent version of text of a specific revision.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        revision_id: ID of the revision whose text we want to retrieve.

    Returns:
        The text of the specified revision.

    Raises:
        RevisionNotFoundException: Revision with corresponding ID is not in database (or insufficient permissions to view it).
        RevisionTextNotFoundException: Text for the specified revision is not found.
    """
    rt = aliased(models.RevisionText)
    q = (
        select(models.RevisionText)
        .where(models.RevisionText.revision_id == revision_id)
        .where(
            models.RevisionText.revision_text_version
            == select(rt.revision_text_version)
            .where(rt.revision_id == revision_id)
            .order_by(rt.revision_text_version.desc())
            .limit(1)
            .scalar_subquery()
        )
    )
    try:
        q = revision_text_mod_access_select(q, current_user)
        result = db.execute(q)
        result_row = result.scalar_one()
    except NoResultFound as e:
        query_revision_by_id(db, current_user, revision_id)
        raise RevisionTextNotFoundException from e
    return result_row


def query_revision_text_by_id(
    db: Session, current_user: User | None, revision_text_id: uuid.UUID
) -> models.RevisionText:
    """
    Query a specific version of text of a specific revision by the text's id.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        revision_text_id: ID of the text we want to retrieve.

    Raises:
        RevisionTextNotFoundException: Text with corresponding ID is not found in database (or insufficient permissions to view it).
    """
    q = select(models.RevisionText).where(models.RevisionText.revision_text_id == revision_text_id)
    q = revision_text_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        result_row = result.scalar_one()
    except NoResultFound as e:
        raise RevisionTextNotFoundException from e
    return result_row


def query_revision_text_status(
    db: Session,
    current_user: User | None,
    revision_id: uuid.UUID,
    revision_text_id: uuid.UUID,
) -> OperationStatus:
    """
    Check whether a revision_text_id is the latest version for its revision.
    Queries the most recent revision text version with read permissions applied,
    then compares against the provided revision_text_id.

    Args:
        db: Database from which we are querying.
        current_user: User performing the check.
        revision_id: ID of the revision to check.
        revision_text_id: ID of the revision text to validate as current.

    Raises:
        RevisionTextNotFoundException: No revision text found for revision_id (or insufficient read permissions).
        RevisionTextOutdatedException: Revision text exists but revision_text_id is not the latest version.
    """
    q = (
        select(models.RevisionText.revision_text_id)
        .where(models.RevisionText.revision_id == revision_id)
        .where(
            models.RevisionText.revision_text_version
            == select(func.max(models.RevisionText.revision_text_version))
            .where(models.RevisionText.revision_id == revision_id)
            .scalar_subquery()
        )
    )
    q = revision_text_mod_access_select(q, current_user)
    try:
        latest_id = db.execute(q).scalar_one()
    except NoResultFound as e:
        raise RevisionTextNotFoundException from e
    if latest_id != revision_text_id:
        raise RevisionTextOutdatedException("Revision text is outdated. Please refresh and try again.")
    return OperationStatus(status="success", detail="Revision text is current.")


def query_revision_text_ids_by_revision_id(
    db: Session, current_user: User, revision_id: uuid.UUID
) -> list[schemas.RevisionTextMeta]:
    """
    Query all text ids of a specific revision.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        revision_id: ID of the revision whose text ids we want to retrieve.
    """
    q = (
        select(models.RevisionText)
        .options(defer(models.RevisionText.revision_text_content))
        .where(models.RevisionText.revision_id == revision_id)
    )
    q = revision_text_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()
    return [schemas.RevisionTextMeta.model_validate(row) for row in result_rows]


def insert_novel(db: Session, current_user: User, request: schemas.CreateNovel) -> models.Novel:
    """
    Insert a novel into the database.

    Args:
        db: Database which we are inserting into.
        current_user: User performing the insert. Only users/admins can create novels.
        request: Metadata of novel.

    Raises:
        LanguageNotFoundException: Language id in request does not exist.
        DataTooLongException: String is too long in some field of data we are inserting.
        UnknownError: Some other error occured.
    """
    novel = models.Novel(**request.model_dump())
    try:
        db.add(novel)
        db.flush()
        contributor = models.Contributor(
            contributor_role=Role.OWNER, novel_id=novel.novel_id, user_id=current_user.user_id
        )
        db.add(contributor)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise LanguageNotFoundException from e
        raise UnknownError from e
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise UnknownError from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
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
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        query_novel_by_id(db, current_user, novel_id)
        raise InsufficientPermissionsException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e

    return result_row


def insert_chapter(
    db: Session, current_user: User, novel_id: uuid.UUID, request: schemas.CreateChapter
) -> models.Chapter:
    """
    Insert a chapter into a database.

    Args:
        db: Database into which we are inserting the chapter.
        current_user: User performing the insert.
        novel_id: id of novel the chapter belongs to
        request: Data to insert.

    Raises:
        NovelNotFoundException: Novel with novel_id does not exist in database (or insufficient permissions to view it).
        InsufficientPermissionsException: User does not have permission to insert a chapter for this novel.
        ChapterNumDuplicateException: Chapter with chapter_num already exists in db.
        UnknownError: Some other error occured.
    """
    data = list(request.model_dump().items())
    data.append(("novel_id", novel_id))
    cols = [k for k, _ in data]

    vals = select(*[literal(v) for _, v in data])
    vals = chapter_mod_access_insert(vals, current_user, novel_id)
    stmt = insert(models.Chapter).from_select(cols, vals).returning(models.Chapter)

    try:
        result = db.execute(stmt)
        result_row = result.scalar_one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise NovelNotFoundException from e
            if pgcode == errorcodes.UNIQUE_VIOLATION:
                raise ChapterNumDuplicateException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        query_novel_by_id(db, current_user, novel_id)
        raise InsufficientPermissionsException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return result_row


def insert_revision(
    db: Session, current_user: User, chapter_id: uuid.UUID, request: schemas.CreateRevision
) -> tuple[models.Revision, models.RevisionText]:
    """
    Insert a chapter revision into the database.

    Args:
        db: Database into which we are adding the revision.
        current_user: User performing insert.
        chapter_id: id of chapter this revision belongs to.
        request: Data to insert.

    Raises:
        ChapterNotFoundException: Chapter with chapter_id does not exist in database (or insufficient permissions to view it).
        InsufficientPermissionsException: User does not have permission to insert a revision for this chapter.
        DataTooLongException: String field we are trying to insert too long.
        UnknownError: Some other error occured.
    """
    data = list(request.model_dump().items())
    data.extend([("chapter_id", chapter_id), ("revision_is_primary", False), ("revision_is_public", False)])
    cols = [k for k, _ in data]

    vals = select(*[literal(v) for _, v in data])
    vals = revision_mod_access_insert(vals, current_user, chapter_id)

    stmt = insert(models.Revision).from_select(cols, vals).returning(models.Revision)
    try:
        result = db.execute(stmt)
        new_revision = result.scalar_one()
        vals = select(literal(new_revision.revision_id), literal(""), literal(1))
        vals = revision_text_mod_access_insert(vals, current_user, new_revision.revision_id)
        cols = ["revision_id", "revision_text_content", "revision_text_version"]
        stmt = insert(models.RevisionText).from_select(cols, vals).returning(models.RevisionText)
        new_revision_text = db.execute(stmt).scalar_one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise ChapterNotFoundException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        query_chapter_by_id(db, current_user, chapter_id)
        raise InsufficientPermissionsException from e
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise UnknownError from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return new_revision, new_revision_text


def modify_revision(
    db: Session,
    current_user: User,
    revision_id: uuid.UUID,
    request: schemas.UpdateRevision,
) -> models.Revision:
    """
    Modifies data of revision with revision_id. Cannot modify public revisions.

    Args:
        db: Database that contains the revision to modify.
        current_user: User performing the update.
        revision_id: id of revision we are modifying.

    Raises:
        RevisionNotFoundException: revision_id does not correspond to a revision in db (or insufficient permissions to view it).
        InsufficientPermissionsException: User does not have permission to modify this revision.
        DataTooLongException: String we are trying to modify is too long.
        UnknownError: Some other error occured.
    """
    stmt = (
        update(models.Revision)
        .where(models.Revision.revision_id == revision_id)
        .values(request.model_dump(exclude_unset=True))
    )
    stmt = revision_mod_access_update(stmt, current_user)
    stmt = stmt.returning(models.Revision)
    try:
        result = db.execute(stmt)
        revision = result.scalar_one()
        db.commit()
    except DataError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
                raise DataTooLongException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        query_revision_by_id(db, current_user, revision_id)
        raise InsufficientPermissionsException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return revision


def make_public_revision(db: Session, current_user: User, revision_id: uuid.UUID) -> models.Revision:
    """
    Make a revision public.

    Args:
        db: Database in which the data resides.
        current_user: User publishing the revision.
        revision_id: id of the revision we are publishing.

    Raises:
        RevisionNotFoundException: Revision with revision_id not found (or insufficient permissions to view it).
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    stmt = update(models.Revision).where(models.Revision.revision_id == revision_id).values(revision_is_public=True)
    stmt = revision_mod_access_update(stmt, current_user)
    stmt = stmt.returning(models.Revision)
    try:
        result = db.execute(stmt)
        revision = result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        query_revision_by_id(db, current_user, revision_id)
        raise InsufficientPermissionsException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return revision


def make_primary_revision(db: Session, current_user: User, revision_id: uuid.UUID) -> models.Revision:
    """
    Mark a revision as primary. Returns the revision marked as primary.

    Args:
        db: Database in which the data resides.
        current_user: User publishing the revision.
        revision_id: id of the revision we are publishing.

    Raises:
        RevisionNotFoundException: Revision with revision_id not found (or insufficient permissions to view it).
        RevisionMakePrimaryFailedException: Failed during the db commit.
        RevisionNotPublicException: Trying to make a non-public revision primary.
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    stmt = (
        update(models.Revision)
        .where(models.Revision.revision_id != revision_id)
        .where(models.Revision.revision_is_primary.is_(True))
        .where(
            models.Revision.chapter_id
            == select(models.Revision.chapter_id).where(models.Revision.revision_id == revision_id).scalar_subquery()
        )
        .values(revision_is_primary=False)
    )
    stmt = revision_mod_access_update(stmt, current_user)

    stmt2 = update(models.Revision).where(models.Revision.revision_id == revision_id).values(revision_is_primary=True)
    stmt2 = revision_mod_access_update(stmt2, current_user)
    stmt2 = stmt2.returning(models.Revision)
    try:
        db.execute(stmt)
        result = db.execute(stmt2)
        revision = result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        query_revision_by_id(db, current_user, revision_id)
        raise InsufficientPermissionsException from e
    except IntegrityError as e:
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.UNIQUE_VIOLATION:
                raise RevisionMakePrimaryFailedException("Only one primary revision allowed per chapter.") from e
            if e.orig.pgcode == errorcodes.CHECK_VIOLATION:  # extra check
                raise RevisionNotPublicException from e
        raise UnknownError from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return revision


def modify_revision_text(
    db: Session,
    current_user: User,
    revision_id: uuid.UUID,
    revision_text_id: uuid.UUID,
    ops: list[schemas.TextOp],
) -> OperationStatus:
    """
    Modify the text of a revision and port all label datas over, including those the current user does not have access to.

    Args:
        db: Database in which the data resides.
        current_user: User performing the update.
        revision_id: id of the revision we are modifying.
        revision_text_id: id of the text we are modifying.
        ops: List of text operations to apply.

    Raises:
        RevisionTextNotFoundException: Revision text with revision_text_id not found (or insufficient permissions to view it).
        RevisionTextOutdatedException: Revision text is outdated.
        UnknownError: Some other error occured.
    """
    q = (
        select(models.RevisionText)
        .where(models.RevisionText.revision_id == revision_id)
        .where(
            models.RevisionText.revision_text_version
            == select(func.max(models.RevisionText.revision_text_version))
            .where(models.RevisionText.revision_id == revision_id)
            .scalar_subquery()
        )
    )
    q = revision_text_mod_access_select(q, current_user)
    try:
        result = db.execute(q)
        revision_text = result.scalar_one()
    except NoResultFound as e:
        raise RevisionTextNotFoundException from e
    if revision_text.revision_text_id != revision_text_id:
        raise RevisionTextOutdatedException("Revision text is outdated. Please refresh and try again.")

    content = revision_text.revision_text_content

    q = (
        select(label_models.Label)
        .join(label_models.LabelData, label_models.Label.label_data_id == label_models.LabelData.label_data_id)
        .where(label_models.LabelData.revision_text_id == revision_text.revision_text_id)
    )
    label_result = db.execute(q).scalars().all()

    labels = [label_schemas.Label.model_validate(label) for label in label_result]

    new_content, new_labels = apply_text_ops(content, ops, labels)

    vals = select(
        literal(revision_text.revision_id), literal(new_content), literal(revision_text.revision_text_version + 1)
    )
    cols = ["revision_id", "revision_text_content", "revision_text_version"]
    vals = revision_text_mod_access_insert(vals, current_user, revision_id)
    stmt = insert(models.RevisionText).from_select(cols, vals).returning(models.RevisionText.revision_text_id)

    try:
        result = db.execute(stmt)
        new_revision_text_id = result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        # Distinguish between outdated text and insufficient write permissions.
        # query_revision_text_status raises the appropriate exception.
        query_revision_text_status(db, current_user, revision_id, revision_text_id)
        # If status check passes (shouldn't happen), raise generic error.
        raise InsufficientPermissionsException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e

    # port label datas
    label_data_map: dict[uuid.UUID, list[label_schemas.Label]] = defaultdict(list)

    for label in new_labels:
        label_data_map[label.label_data_id].append(label)

    for label_data_id, labels in label_data_map.items():
        label_data_q = select(label_models.LabelData.label_group_id).where(
            label_models.LabelData.label_data_id == label_data_id
        )
        label_group_id = db.execute(label_data_q).scalar_one()
        stmt = (
            insert(label_models.LabelData)
            .values(label_group_id=label_group_id, revision_text_id=new_revision_text_id)
            .returning(label_models.LabelData)
        )
        label_data = db.execute(stmt).scalar_one()
        label_vals = [label.model_dump() for label in labels]
        for label in label_vals:
            label["label_data_id"] = label_data.label_data_id
        stmt = insert(label_models.Label).values(label_vals)
        db.execute(stmt)
    db.commit()

    return OperationStatus(status="success", detail="Revision text modified successfully.")


def remove_revision(db: Session, current_user: User, revision_id: uuid.UUID) -> OperationStatus:
    """
    Remove a revision from the database.

    Args:
        db: Database to remove from.
        current_user: User removing the chapter.
        revision_id: id of revision to remove.

    Raises:
        RevisionNotFoundException: Revision with revision_id not found (or insufficient permissions to view it).
        InsufficientPermissionsException: Current user has insufficient permissions to delete this chapter.
        DeleteRevisionFailedException: Delete failed for other reasons.
    """
    stmt = delete(models.Revision).where(models.Revision.revision_id == revision_id)
    stmt = revision_mod_access_delete(stmt, current_user)
    try:
        result = db.execute(stmt)
        cursor_res = cast(CursorResult[Any], result)
        if cursor_res.rowcount == 0:
            db.rollback()
            query_revision_by_id(db, current_user, revision_id)
            raise InsufficientPermissionsException
        db.commit()
    except InsufficientPermissionsException as e:
        raise e
    except RevisionNotFoundException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise DeleteRevisionFailedException from e
    return OperationStatus(status="success", detail="Delete succeeded.")


# --- Novel Association ---


def query_novel_associations(
    db: Session, current_user: User | None, source_novel_id: uuid.UUID
) -> list[models.NovelAssociation]:
    """
    Query all novel associations for a given source novel.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying. Can be None for guest access.
        source_novel_id: UUID of the source novel.

    Raises:
        NovelNotFoundException: Source novel not found or insufficient permissions.
    """
    # Verify the source novel is accessible
    query_novel_by_id(db, current_user, source_novel_id)

    q = select(models.NovelAssociation).where(models.NovelAssociation.source_novel_id == source_novel_id)
    result = db.execute(q)
    return list(result.scalars().all())


def insert_novel_association(
    db: Session, current_user: User, request: schemas.CreateNovelAssociation
) -> models.NovelAssociation:
    """
    Insert a novel association into the database. Requires owner or editor role on the source novel.

    Args:
        db: Database into which we are inserting.
        current_user: User performing the insert.
        request: Data for the association to create.

    Raises:
        NovelNotFoundException: Source or target novel not found or insufficient permissions.
        DuplicateNovelAssociationException: Association with same (source, target, type) already exists.
        UnknownError: Some other error occurred.
    """
    # Verify source novel is accessible and user has edit rights
    vals = select(
        literal(request.source_novel_id),
        literal(request.target_novel_id),
        literal(str(request.association_type)),
    )
    vals = chapter_mod_access_insert(vals, current_user, request.source_novel_id)

    cols = ["source_novel_id", "target_novel_id", "association_type"]
    stmt = insert(models.NovelAssociation).from_select(cols, vals).returning(models.NovelAssociation)

    try:
        result = db.execute(stmt)
        association = result.scalar_one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.UNIQUE_VIOLATION:
                raise DuplicateNovelAssociationException from e
            if e.orig.pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise NovelNotFoundException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        query_novel_by_id(db, current_user, request.source_novel_id)
        raise InsufficientPermissionsException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return association


def remove_novel_association(db: Session, current_user: User, association_id: uuid.UUID) -> None:
    """
    Remove a novel association from the database. Requires owner or editor role on the source novel.

    Args:
        db: Database to remove from.
        current_user: User performing the removal.
        association_id: UUID of the association to remove.

    Raises:
        NovelAssociationNotFoundException: Association not found or insufficient permissions.
        UnknownError: Some other error occurred.
    """
    from ..auth.constants import UserType

    stmt = delete(models.NovelAssociation).where(models.NovelAssociation.association_id == association_id)
    if current_user.user_type != UserType.ADMIN:
        stmt = stmt.where(
            exists(
                select(1)
                .select_from(models.Contributor)
                .where(models.Contributor.novel_id == models.NovelAssociation.source_novel_id)
                .where(models.Contributor.user_id == current_user.user_id)
                .where(models.Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    stmt = stmt.returning(models.NovelAssociation.association_id)
    try:
        result = db.execute(stmt)
        _ = result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        raise NovelAssociationNotFoundException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
