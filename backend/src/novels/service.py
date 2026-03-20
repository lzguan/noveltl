"""
Service functions for novels/chapters.

Todo:
    Implement user permissions.
"""

from collections.abc import Sequence
from typing import Any, cast

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
    ChapterNotFoundException,
    ChapterNumDuplicateException,
    DeleteRevisionFailedException,
    NovelNotFoundException,
    RevisionMakePrimaryFailedException,
    RevisionNotFoundException,
    RevisionNotPublicException,
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

def query_chapters_by_novel(
        db : Session,
        current_user : User | None,
        novel_id : int,
        start : int | None,
        end : int | None
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
    q = select(
        models.Chapter
    ).select_from(
        models.Novel
    ).where(
        models.Novel.novel_id == novel_id
    ).join(
        models.Chapter,
        models.Chapter.novel_id == models.Novel.novel_id
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

def query_chapter_by_id(
        db : Session,
        current_user : User | None,
        chapter_id : int
    ) -> models.Chapter:
    """
    Query a chapter by id.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        chapter_id: id of chapter we are querying from.

    Raises:
        ChapterNotFoundException: Chapter not found in database (or insufficient permissions to view it).
    """
    q = select(
        models.Chapter
    ).where(
        models.Chapter.chapter_id == chapter_id
    ).join(
        models.Novel,
        models.Chapter.novel_id == models.Novel.novel_id
    )
    q = chapter_mod_access_select(q, current_user)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise ChapterNotFoundException from e
    return result_scalar

def query_revision_by_id(
        db : Session,
        current_user : User | None,
        revision_id : int
    ) -> models.Revision:
    """
    Query a chapter revision by id.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        revision_id: id of chapter revision we are querying.

    Raises:
        RevisionNotFoundException: Chapter revision not found in database (or insufficient permissions to view it).
    """
    q = select(
        models.Revision
    ).where(
        models.Revision.revision_id == revision_id
    ).join(
        models.Chapter,
        models.Chapter.chapter_id == models.Revision.chapter_id
    ).join(
        models.Novel,
        models.Novel.novel_id == models.Chapter.novel_id
    )
    q = revision_mod_access_select(q, current_user)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise RevisionNotFoundException from e
    return result_scalar

def query_revisions_by_chapter(
        db : Session,
        current_user : User | None,
        chapter_id : int,
        is_public : bool | None,
        is_primary : bool | None
    ) -> list[schemas.RevisionMeta]:
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
    q = select(
        models.Revision
    ).options(
        defer(models.Revision.revision_text)
    ).where(
        models.Revision.chapter_id == chapter_id
    ).join(
        models.Chapter,
        models.Chapter.chapter_id == models.Revision.chapter_id
    ).join(
        models.Novel,
        models.Novel.novel_id == models.Chapter.novel_id
    ).order_by(
        models.Revision.revision_is_primary.desc(),
        models.Revision.revision_is_public.desc(),
        models.Revision.updated_at.desc()
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
    return [schemas.RevisionMeta.model_validate(row) for row in result_rows]

def query_revisions_by_novel(
        db : Session,
        current_user : User | None,
        novel_id : int,
        start : int | None,
        end : int | None,
        is_public : bool | None,
        is_primary : bool | None,
        is_final : bool | None
    ) -> list[schemas.RevisionMeta]:
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
        is_final: If not None, then filter novels by final status.

    Raises:
        NovelNotFoundException: novel with corresponding novel_id is not in database (or insufficient permissions to view it).
    """
    q = select(models.Revision).options(
        defer(models.Revision.revision_text)
    ).select_from(
        models.Revision
    ).join(
        models.Chapter, models.Chapter.chapter_id == models.Revision.chapter_id
    ).join(
        models.Novel,
        models.Novel.novel_id == models.Chapter.novel_id
    ).where(
        models.Novel.novel_id == novel_id
    ).order_by(
        models.Chapter.chapter_num.asc(),
        models.Revision.revision_is_primary.desc(),
        models.Revision.revision_is_public.desc(),
        models.Revision.updated_at.desc()
    )
    if start is not None:
        q = q.where(models.Chapter.chapter_num >= start)
    if end is not None:
        q = q.where(models.Chapter.chapter_num < end)
    if is_public is not None:
        q = q.where(models.Revision.revision_is_public == is_public)
    if is_primary is not None:
        q = q.where(models.Revision.revision_is_primary == is_primary)
    if is_final is not None:
        q = q.where(models.Revision.revision_is_final == is_final)
    q = revision_mod_access_select(q, current_user)
    result = db.execute(q)
    result_rows  = result.scalars().all()
    if len(result_rows) == 0:
        query_novel_by_id(db, current_user, novel_id)
    return [schemas.RevisionMeta.model_validate(row) for row in result_rows]

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

def insert_chapter(
        db : Session,
        current_user : User,
        novel_id : int,
        request : schemas.CreateChapter
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
    data.append(('novel_id', novel_id))
    cols = [k for k, _ in data]

    vals = select(
        *[literal(v) for _, v in data]
    )
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
        db : Session,
        current_user : User,
        chapter_id : int,
        request : schemas.CreateRevision
    ) -> models.Revision:
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
    data.extend([('chapter_id', chapter_id), ('revision_is_primary', False), ('revision_is_public', False), ('revision_is_final', False)])
    cols = [k for k, _ in data]

    vals = select(
        *[literal(v) for _, v in data]
    )
    vals = revision_mod_access_insert(vals, current_user, chapter_id)

    stmt = insert(models.Revision).from_select(cols, vals).returning(models.Revision)
    try:
        result = db.execute(stmt)
        new_revision = result.scalar_one()
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
    return new_revision

def modify_revision(
        db : Session,
        current_user : User,
        revision_id : int,
        request : schemas.UpdateRevision,
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
    stmt = update(
        models.Revision
    ).where(
        models.Revision.revision_id == revision_id
    ).where(models.Revision.revision_is_final.is_(False)).values(
        request.model_dump(exclude_unset=True)
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

def make_public_revision(
        db : Session,
        current_user : User,
        revision_id : int
) -> models.Revision:
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
    stmt = update(
        models.Revision
    ).where(
        models.Revision.revision_id == revision_id
    ).values(
        revision_is_public = True
    )
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

def make_primary_revision(db : Session, current_user : User, revision_id : int) -> models.Revision:
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
    stmt = update(
        models.Revision
    ).where(
        models.Revision.revision_id != revision_id
    ).where(
        models.Revision.revision_is_primary.is_(True)
    ).where(
        models.Revision.chapter_id == select(
            models.Revision.chapter_id
        ).where(
            models.Revision.revision_id == revision_id
        ).scalar_subquery()
    ).values(revision_is_primary=False)
    stmt = revision_mod_access_update(stmt, current_user)

    stmt2 = update(
        models.Revision
    ).where(
        models.Revision.revision_id == revision_id
    ).values(
        revision_is_primary = True
    )
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
            if e.orig.pgcode == errorcodes.CHECK_VIOLATION: # extra check
                raise RevisionNotPublicException from e
        raise UnknownError from e
    except Exception as e:
        db.rollback()
        raise UnknownError from e
    return revision

def make_final_revision(
        db : Session,
        current_user : User,
        revision_id : int
) -> models.Revision:
    """
    Make a revision final.

    Args:
        db: Database in which the data resides.
        current_user: User finalizing the revision.
        revision_id: id of the revision we are finalizing.

    Raises:
        RevisionNotFoundException: Revision with revision_id not found (or insufficient permissions to view it).
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    stmt = update(
        models.Revision
    ).where(
        models.Revision.revision_id == revision_id
    ).values(
        revision_is_final = True
    )
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

def remove_revision(
        db : Session,
        current_user : User,
        revision_id : int
    ) -> schemas.DeleteRevisionStatus:
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
    stmt = delete(
        models.Revision
    ).where(
        models.Revision.revision_id == revision_id
    )
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
    return schemas.DeleteRevisionStatus(status="success", detail="Delete succeeded.")
