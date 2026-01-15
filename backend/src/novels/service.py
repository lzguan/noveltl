"""
Service functions for novels/chapters.

Todo:
    Implement user permissions.
"""

from collections.abc import Sequence
from typing import cast

from psycopg2 import Error as PgError
from psycopg2 import errorcodes
from sqlalchemy import CursorResult, and_, delete, exists, insert, literal, select, update
from sqlalchemy.exc import DataError, IntegrityError, NoResultFound
from sqlalchemy.orm import Session, defer

from ..auth.models import User
from ..exceptions import DataTooLongException, InsufficientPermissionsException, UnknownError
from ..languages.exceptions import LanguageNotFoundException
from . import models, schemas
from .constants import Role, Visibility
from .exceptions import (
    ChapterNumDuplicateException,
    DeleteRawChapterRevisionFailedException,
    NovelNotFoundException,
    RawChapterNotFoundException,
    RawChapterRevisionMakePrimaryFailedException,
    RawChapterRevisionNotFoundException,
    RawChapterRevisionNotPublicException,
)
from .permissions import (
    novel_mod_access_select,
    novel_mod_access_update,
    raw_chapter_mod_access_insert,
    raw_chapter_mod_access_select,
    raw_chapter_revision_mod_access_delete,
    raw_chapter_revision_mod_access_insert,
    raw_chapter_revision_mod_access_select,
    raw_chapter_revision_mod_access_update,
)


def query_novels_by_title(
        db : Session,
        current_user : User | None,
        novel_title : str | None
    ) -> Sequence[models.Novel]:
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
    q = select(models.Novel).where(models.Novel.novel_title.ilike(search_term)).where(models.Novel.novel_visibility == Visibility.PUBLIC)
    result = db.execute(q)
    result_scalars = result.scalars().all()

    return result_scalars

def query_novels_by_current_user(
        db : Session,
        current_user : User,
        editable : bool,
        title_contains : str | None
    ) -> list[models.Novel]:
    """
    Queries all novels that the current user has special access to.

    Args:
        db: Database from which we are querying from.
        current_user: User that is querying.
        editable: If True, only select novels that the user can edit. Otherwise select all such novels.
    """
    subq = select(models.Contributor).where(and_(
        models.Contributor.novel_id == models.Novel.novel_id,
        models.Contributor.user_id == current_user.user_id
    ))
    if editable:
        subq = subq.where(models.Contributor.contributor_role.in_([Role.EDITOR, Role.OWNER]))
    q = select(
        models.Novel
    ).where(exists(subq))

    if title_contains:
        q = q.where(models.Novel.novel_title.ilike(f"%{title_contains}%"))

    result = db.execute(q)
    result_scalars = result.scalars().all()
    return list(result_scalars)

def query_novel_by_id(
        db : Session,
        current_user : User | None,
        novel_id : int
    ) -> models.Novel:
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

def query_raw_chapters_by_novel(
        db : Session,
        current_user : User | None,
        novel_id : int,
        start : int | None,
        end : int | None
    ) -> Sequence[models.RawChapter]:
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
    q = select(
        models.RawChapter
    ).select_from(
        models.Novel
    ).where(
        models.Novel.novel_id == novel_id
    ).join(
        models.RawChapter,
        models.RawChapter.novel_id == models.Novel.novel_id
    )
    if start is not None:
        q = q.where(models.RawChapter.raw_chapter_num >= start)
    if end is not None:
        q = q.where(models.RawChapter.raw_chapter_num < end)
    q = raw_chapter_mod_access_select(q, current_user)
    q = q.order_by(models.RawChapter.raw_chapter_num.asc())
    result = db.execute(q)
    result_scalars = result.scalars().all()
    if len(result_scalars) == 0:
        query_novel_by_id(db, current_user, novel_id)
    return result_scalars

def query_raw_chapter_by_id(
        db : Session,
        current_user : User | None,
        raw_chapter_id : int
    ) -> models.RawChapter:
    """
    Query a chapter by id.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        raw_chapter_id: id of chapter we are querying from.

    Raises:
        RawChapterNotFoundException: Chapter not found in database (or insufficient permissions to view it).
    """
    q = select(
        models.RawChapter
    ).where(
        models.RawChapter.raw_chapter_id == raw_chapter_id
    ).join(
        models.Novel,
        models.RawChapter.novel_id == models.Novel.novel_id
    )
    q = raw_chapter_mod_access_select(q, current_user)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise RawChapterNotFoundException from e
    return result_scalar

def query_raw_chapter_revision_by_id(
        db : Session,
        current_user : User | None,
        raw_chapter_revision_id : int
    ) -> models.RawChapterRevision:
    """
    Query a chapter revision by id.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        raw_chapter_revision_id: id of chapter revision we are querying.

    Raises:
        RawChapterRevisionNotFoundException: Chapter revision not found in database (or insufficient permissions to view it).
    """
    q = select(
        models.RawChapterRevision
    ).where(
        models.RawChapterRevision.raw_chapter_revision_id == raw_chapter_revision_id
    ).join(
        models.RawChapter,
        models.RawChapter.raw_chapter_id == models.RawChapterRevision.raw_chapter_id
    ).join(
        models.Novel,
        models.Novel.novel_id == models.RawChapter.novel_id
    )
    q = raw_chapter_revision_mod_access_select(q, current_user)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise RawChapterRevisionNotFoundException from e
    return result_scalar

def query_raw_chapter_revisions_by_raw_chapter(
        db : Session,
        current_user : User | None,
        raw_chapter_id : int,
        is_public : bool | None,
        is_primary : bool | None
    ) -> list[schemas.RawChapterRevisionMeta]:
    """
    Query all chapter revisions from a raw_chapter_id satisfying certain requirements.

    Args:
        db: Database from which we are querying.
        current_user: User performing the query.
        raw_chapter_id: id of chapter we are querying from.
        is_public: If not None, only select public chapters.
        is_primary: If not None, only select primary chapters.

    Raises:
        RawChapterNotFoundException: Raw chapter with corresponding raw_chapter_id is not in database (or no permissions to view it).
    Notes:
        The caller should be responsible for converting to the best pydantic model for the use case.
    """
    q = select(
        models.RawChapterRevision
    ).options(
        defer(models.RawChapterRevision.raw_chapter_revision_text)
    ).where(
        models.RawChapterRevision.raw_chapter_id == raw_chapter_id
    ).join(
        models.RawChapter,
        models.RawChapter.raw_chapter_id == models.RawChapterRevision.raw_chapter_id
    ).join(
        models.Novel,
        models.Novel.novel_id == models.RawChapter.novel_id
    ).order_by(
        models.RawChapterRevision.raw_chapter_revision_is_primary.desc(),
        models.RawChapterRevision.raw_chapter_revision_is_public.desc(),
        models.RawChapterRevision.updated_at.desc()
    )
    if is_public is not None:
        q = q.where(models.RawChapterRevision.raw_chapter_revision_is_public == is_public)
    if is_primary is not None:
        q = q.where(models.RawChapterRevision.raw_chapter_revision_is_primary == is_primary)
    q = raw_chapter_revision_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows = result.scalars().all()
    if len(result_rows) == 0:
        query_raw_chapter_by_id(db, current_user, raw_chapter_id)
    return [schemas.RawChapterRevisionMeta.model_validate(row) for row in result_rows]

def query_raw_chapter_revisions_by_novel(
        db : Session,
        current_user : User | None,
        novel_id : int,
        start : int | None,
        end : int | None,
        is_public : bool | None,
        is_primary : bool | None,
        is_final : bool | None
    ) -> list[schemas.RawChapterRevisionMeta]:
    """
    Query all chapter revisions from novel novel_id satisfying certain restrictions. Returns a dictionary in the format
        `chapter_num : List[RawChapterRevisionMeta]`

    Args:
        db: Database from which we are querying from.
        current_user: User that is querying.
        novel_id: id of novel we are querying chapter revisions from.
        start: If not None, then only query chapter revisions that have chapter_num >= start.
        end: If not None, then only query chapter revisions that have chapter_num < end.
        is_public: If not None, then filter novels by public status.
        is_primary: If not None, then filter novels by primary status.
        is_final: If not None, then filter novels by final status.

    Raises:
        NovelNotFoundException: novel with corresponding novel_id is not in database (or insufficient permissions to view it).
    """
    q = select(models.RawChapterRevision).options(
        defer(models.RawChapterRevision.raw_chapter_revision_text)
    ).select_from(
        models.RawChapterRevision
    ).join(
        models.RawChapter, models.RawChapter.raw_chapter_id == models.RawChapterRevision.raw_chapter_id
    ).join(
        models.Novel,
        models.Novel.novel_id == models.RawChapter.novel_id
    ).where(
        models.Novel.novel_id == novel_id
    ).order_by(
        models.RawChapter.raw_chapter_num.asc(),
        models.RawChapterRevision.raw_chapter_revision_is_primary.desc(),
        models.RawChapterRevision.raw_chapter_revision_is_public.desc(),
        models.RawChapterRevision.updated_at.desc()
    )
    if start is not None:
        q = q.where(models.RawChapter.raw_chapter_num >= start)
    if end is not None:
        q = q.where(models.RawChapter.raw_chapter_num < end)
    if is_public is not None:
        q = q.where(models.RawChapterRevision.raw_chapter_revision_is_public == is_public)
    if is_primary is not None:
        q = q.where(models.RawChapterRevision.raw_chapter_revision_is_primary == is_primary)
    if is_final is not None:
        q = q.where(models.RawChapterRevision.raw_chapter_revision_is_final == is_final)
    q = raw_chapter_revision_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows  = result.scalars().all()
    if len(result_rows) == 0:
        query_novel_by_id(db, current_user, novel_id)
    return [schemas.RawChapterRevisionMeta.model_validate(row) for row in result_rows]

def insert_novel(
        db : Session,
        current_user : User,
        request : schemas.CreateNovel
    ) -> models.Novel:
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
        contributor = models.Contributor(contributor_role=Role.OWNER, novel_id=novel.novel_id, user_id=current_user.user_id)
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

def modify_novel(
        db : Session,
        current_user : User,
        novel_id : int,
        request : schemas.UpdateNovel
    ) -> models.Novel:
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
    stmt = update(
        models.Novel
    ).where(
        models.Novel.novel_id == novel_id
    ).values(request.model_dump(exclude_unset=True))
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

def insert_raw_chapter(
        db : Session,
        current_user : User,
        novel_id : int,
        request : schemas.CreateRawChapter
    ) -> models.RawChapter:
    """
    Insert a raw chapter into a database.

    Args:
        db: Database into which we are inserting the raw chapter.
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
    data.append(('novel_id', novel_id))
    cols = [k for k, _ in data]

    vals = select(
        *[literal(v) for _, v in data]
    )
    vals = raw_chapter_mod_access_insert(vals, current_user, novel_id)
    stmt = insert(models.RawChapter).from_select(cols, vals).returning(models.RawChapter)

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

def insert_raw_chapter_revision(
        db : Session,
        current_user : User,
        raw_chapter_id : int,
        request : schemas.CreateRawChapterRevision
    ) -> models.RawChapterRevision:
    """
    Insert a raw chapter revision into the database.

    Args:
        db: Database into which we are adding the revision.
        current_user: User performing insert.
        raw_chapter_id: id of raw chapter this revision belongs to.
        request: Data to insert.

    Raises:
        RawChapterNotFoundException: Raw chapter with raw_chapter_id does not exist in database (or insufficient permissions to view it).
        InsufficientPermissionsException: User does not have permission to insert a revision for this raw chapter.
        DataTooLongException: String field we are trying to insert too long.
        UnknownError: Some other error occured.
    """
    data = list(request.model_dump().items())
    data.extend([('raw_chapter_id', raw_chapter_id), ('raw_chapter_revision_is_primary', False), ('raw_chapter_revision_is_public', False), ('raw_chapter_revision_is_final', False)])
    cols = [k for k, _ in data]

    vals = select(
        *[literal(v) for _, v in data]
    )
    vals = raw_chapter_revision_mod_access_insert(vals, current_user, raw_chapter_id)

    stmt = insert(models.RawChapterRevision).from_select(cols, vals).returning(models.RawChapterRevision)
    try:
        result = db.execute(stmt)
        new_revision = result.scalar_one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, PgError):
            pgcode = e.orig.pgcode
            if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
                raise RawChapterNotFoundException from e
        raise UnknownError from e
    except NoResultFound as e:
        db.rollback()
        query_raw_chapter_by_id(db, current_user, raw_chapter_id)
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
    return new_revision

def modify_raw_chapter_revision(
        db : Session,
        current_user : User,
        revision_id : int,
        request : schemas.UpdateRawChapterRevision,
    ) -> models.RawChapterRevision:
    """
    Modifies data of raw chapter revision with revision_id. Cannot modify public revisions.

    Args:
        db: Database that contains the raw chapter revision to modify.
        current_user: User performing the update.
        revision_id: id of raw chapter revision we are modifying.

    Raises:
        RawChapterRevisionNotFoundException: raw_chapter_revision_id does not correspond to a raw chapter revision in db (or insufficient permissions to view it).
        InsufficientPermissionsException: User does not have permission to modify this raw chapter revision.
        DataTooLongException: String we are trying to modify is too long.
        UnknownError: Some other error occured.
    """
    stmt = update(
        models.RawChapterRevision
    ).where(
        models.RawChapterRevision.raw_chapter_revision_id == revision_id
    ).where(models.RawChapterRevision.raw_chapter_revision_is_final.is_(False)).values(
        request.model_dump(exclude_unset=True)
    )
    stmt = raw_chapter_revision_mod_access_update(stmt, current_user)
    stmt = stmt.returning(models.RawChapterRevision)
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
        query_raw_chapter_revision_by_id(db, current_user, revision_id)
        raise InsufficientPermissionsException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return revision

def publish_raw_chapter_revision(
        db : Session,
        current_user : User,
        raw_chapter_revision_id : int
) -> models.RawChapterRevision:
    """
    Make a raw chapter revision public.

    Args:
        db: Database in which the data resides.
        current_user: User publishing the revision.
        raw_chapter_revision_id: id of the revision we are publishing.

    Raises:
        RawChapterRevisionNotFoundException: Raw chapter revision with raw_chapter_revision_id not found (or insufficient permissions to view it).
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    stmt = update(
        models.RawChapterRevision
    ).where(
        models.RawChapterRevision.raw_chapter_revision_id == raw_chapter_revision_id
    ).values(
        raw_chapter_revision_is_public = True
    )
    stmt = raw_chapter_revision_mod_access_update(stmt, current_user)
    stmt = stmt.returning(models.RawChapterRevision)
    try:
        result = db.execute(stmt)
        revision = result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        query_raw_chapter_revision_by_id(db, current_user, raw_chapter_revision_id)
        raise InsufficientPermissionsException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return revision

def make_primary_raw_chapter_revision(db : Session, current_user : User, raw_chapter_revision_id : int) -> models.RawChapterRevision:
    """
    Mark a raw chapter revision as primary. Returns the chapter marked as primary.

    Args:
        db: Database in which the data resides.
        current_user: User publishing the revision.
        raw_chapter_revision_id: id of the revision we are publishing.

    Raises:
        RawChapterRevisionNotFoundException: Raw chapter revision with raw_chapter_revision_id not found (or insufficient permissions to view it).
        RawChapterRevisionMakePrimaryFailedException: Failed during the db commit.
        RawChapterRevisionNotPublicException: Trying to make a non-public revision primary.
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    stmt = update(
        models.RawChapterRevision
    ).where(
        models.RawChapterRevision.raw_chapter_revision_id != raw_chapter_revision_id
    ).where(
        models.RawChapterRevision.raw_chapter_revision_is_primary.is_(True)
    ).where(
        models.RawChapterRevision.raw_chapter_id == select(
            models.RawChapterRevision.raw_chapter_id
        ).where(
            models.RawChapterRevision.raw_chapter_revision_id == raw_chapter_revision_id
        ).scalar_subquery()
    ).values(raw_chapter_revision_is_primary=False)
    stmt = raw_chapter_revision_mod_access_update(stmt, current_user)

    stmt2 = update(
        models.RawChapterRevision
    ).where(
        models.RawChapterRevision.raw_chapter_revision_id == raw_chapter_revision_id
    ).values(
        raw_chapter_revision_is_primary = True
    )
    stmt2 = raw_chapter_revision_mod_access_update(stmt2, current_user)
    stmt2 = stmt2.returning(models.RawChapterRevision)
    try:
        db.execute(stmt)
        result = db.execute(stmt2)
        revision = result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        query_raw_chapter_revision_by_id(db, current_user, raw_chapter_revision_id)
        raise InsufficientPermissionsException from e
    except IntegrityError as e:
        if isinstance(e.orig, PgError):
            if e.orig.pgcode == errorcodes.UNIQUE_VIOLATION:
                raise RawChapterRevisionMakePrimaryFailedException("Only one primary revision allowed per chapter.") from e
            if e.orig.pgcode == errorcodes.CHECK_VIOLATION: # extra check
                raise RawChapterRevisionNotPublicException from e
        raise UnknownError from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return revision

def make_final_raw_chapter_revision(
        db : Session,
        current_user : User,
        raw_chapter_revision_id : int
) -> models.RawChapterRevision:
    """
    Make a raw chapter revision final.

    Args:
        db: Database in which the data resides.
        current_user: User finalizing the revision.
        raw_chapter_revision_id: id of the revision we are finalizing.

    Raises:
        RawChapterRevisionNotFoundException: Raw chapter revision with raw_chapter_revision_id not found (or insufficient permissions to view it).
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    stmt = update(
        models.RawChapterRevision
    ).where(
        models.RawChapterRevision.raw_chapter_revision_id == raw_chapter_revision_id
    ).values(
        raw_chapter_revision_is_final = True
    )
    stmt = raw_chapter_revision_mod_access_update(stmt, current_user)
    stmt = stmt.returning(models.RawChapterRevision)

    try:
        result = db.execute(stmt)
        revision = result.scalar_one()
        db.commit()
    except NoResultFound as e:
        db.rollback()
        query_raw_chapter_revision_by_id(db, current_user, raw_chapter_revision_id)
        raise InsufficientPermissionsException from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return revision

def remove_raw_chapter_revision(
        db : Session,
        current_user : User,
        raw_chapter_revision_id : int
    ) -> schemas.DeleteRawChapterRevisionStatus:
    """
    Remove a raw chapter revision from the database.

    Args:
        db: Database to remove from.
        current_user: User removing the chapter.
        raw_chapter_revision_id: id of revision to remove.

    Raises:
        RawChapterRevisionNotFoundException: Revision with raw_chapter_revision_id not found (or insufficient permissions to view it).
        InsufficientPermissionsException: Current user has insufficient permissions to delete this chapter.
        DeleteRawChapterRevisionFailedException: Delete failed for other reasons.
    """
    stmt = delete(
        models.RawChapterRevision
    ).where(
        models.RawChapterRevision.raw_chapter_revision_id == raw_chapter_revision_id
    )
    stmt = raw_chapter_revision_mod_access_delete(stmt, current_user)
    try:
        result = db.execute(stmt)
        cursor_res = cast(CursorResult, result)
        if cursor_res.rowcount == 0:
            db.rollback()
            query_raw_chapter_revision_by_id(db, current_user, raw_chapter_revision_id)
            raise InsufficientPermissionsException
        db.commit()
    except InsufficientPermissionsException as e:
        raise e
    except RawChapterRevisionNotFoundException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise DeleteRawChapterRevisionFailedException from e
    return schemas.DeleteRawChapterRevisionStatus(status="success", detail="Delete succeeded.")
