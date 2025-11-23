"""
Service functions for novels/chapters.

Todo:
    Implement user permissions.
"""

from . import models
from . import schemas
from .utils import *
from .exceptions import *
from .constants import *
from ..auth.schemas import User
from ..languages.exceptions import LanguageNotFoundException
from sqlalchemy.orm import Session, defer
from typing import List, Dict
from sqlalchemy.exc import IntegrityError, NoResultFound, DataError, MultipleResultsFound
from sqlalchemy import select
from collections import defaultdict
from ..main import logger
from psycopg2 import errorcodes

def query_novels_by_title(
        db : Session, 
        current_user : User | None, 
        novel_title : str | None
    ) -> List[models.Novel]:
    """
    Queries novels with novel_title as substring.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        novel_title: Substring we wish to search for.
    """
    if novel_title is None:
        search_term = "%"
    else:
        search_term = f"%{novel_title}%"
    q = select(models.Novel).where(models.Novel.novel_title.ilike(search_term))
    result = db.execute(q)
    result_scalars = result.scalars().all()
    
    return result_scalars

def query_novel_by_id(
        db : Session, 
        current_user : User | None, 
        novel_id : int
    ) -> models.Novel:
    """
    Queries a novel by id

    Args:
        db: Database from which we are querying.
        current_user: User that is querying.
        novel_id: id of novel in database.
    
    Raises:
        NovelNotFoundException: Novel not found in database.
        NovelTooManyFoundException: Multiple novels with id found in database.
    """
    q = select(models.Novel).where(models.Novel.novel_id == novel_id)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise NovelNotFoundException
    except MultipleResultsFound as e:
        raise NovelTooManyFoundException
    return result_scalar

def query_raw_chapters_by_novel(
        db : Session, 
        current_user : User | None, 
        novel_id : int, 
        start : int | None, 
        end : int | None
    ) -> List[models.RawChapter]:
    """
    Query all chapters of a specific novel satisfying certain conditions.

    Args:
        db: Database from which we are querying.
        current_user: User that is querying. Depending on permissions, will only be allowed to view public chapters. TBD
        novel_id: id of novel we are querying chapters from.
        start: If not none, then only query chapters with chapter_num >= start
        end: If not none, then only query chapters with chapter_num < end
    
    Raises:
    """
    q = select(models.RawChapter).where(models.RawChapter.novel_id == novel_id)
    if start is not None:
        q = q.where(models.RawChapter.raw_chapter_num >= start)
    if end is not None:
        q = q.where(models.RawChapter.raw_chapter_num < end)
    result_scalars = db.execute(q).scalars().all()
    if len(result_scalars) == 0:
        # throws error if novel_id is invalid
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
        RawChapterNotFoundException: Chapter not found in database.
        sqlalchemy.exc.MultipleResultsFound: Multiple chapters with id found in database.
    """
    q = select(models.RawChapter).where(models.RawChapter.raw_chapter_id == raw_chapter_id)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise RawChapterNotFoundException
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
        RawChapterRevisionNotFoundException: If raw_chapter_revision_id does not correspond to a chapter revision.
        InsufficientPermissionsException: If a user does not have permission to access this revision.
    """
    q = select(models.RawChapterRevision).where(models.RawChapterRevision.raw_chapter_revision_id == raw_chapter_revision_id)
    result = db.execute(q)
    try:
        result_scalar = result.scalar_one()
    except NoResultFound as e:
        raise RawChapterRevisionNotFoundException
    return result_scalar

def query_raw_chapter_revisions_by_raw_chapter(
        db : Session,
        current_user : User | None,
        raw_chapter_id : int,
        is_public : bool | None,
        is_primary : bool | None
    ) -> List[models.RawChapterRevision]:
    """
    Query all chapter revisions from a raw_chapter_id satisfying certain requirements.

    Args:
        db: Database from which we are querying.
        current_user: User performing the query.
        raw_chapter_id: id of chapter we are querying from.
        is_public: If not None, only select public chapters.
        is_primary: If not None, only select primary chapters.

    Raises:
        RawChapterNotFoundException: novel with corresponding novel_id is not in database
    Notes:
        The caller should be responsible for converting to the best pydantic model for the use case.
    """
    q = select(models.RawChapterRevision).where(models.RawChapterRevision.raw_chapter_id == raw_chapter_id)
    if is_public is not None:
        q = q.where(models.RawChapterRevision.raw_chapter_revision_is_public == is_public)
    if is_primary is not None:
        q = q.where(models.RawChapterRevision.raw_chapter_revision_is_primary == is_primary)
    
    result = db.execute(q)
    result_rows = result.scalars().all()
    if len(result_rows) == 0:
        query_raw_chapter_by_id(db, current_user, raw_chapter_id)
    return result_rows

def query_raw_chapter_revisions_by_novel(
        db : Session, 
        current_user : User | None,
        novel_id : int, 
        start : int | None, 
        end : int | None, 
        is_public : bool | None, 
        is_primary : bool | None,
        is_final : bool | None
    ) -> Dict[int, List[schemas.RawChapterRevisionMeta]]:
    """
    Query all chapter revisions from novel novel_id satisfying certain restrictions.

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
        NovelNotFoundException: novel with corresponding novel_id is not in database
    """
    q = select(models.RawChapter.raw_chapter_num, models.RawChapterRevision).options(
        defer(models.RawChapterRevision.raw_chapter_revision_text)
    ).join(
        models.RawChapter, models.RawChapter.raw_chapter_id == models.RawChapterRevision.raw_chapter_id
    ).where(
        models.RawChapter.novel_id == novel_id
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
    result = db.execute(q)
    result_rows  = result.all()
    if len(result_rows) == 0:
        query_novel_by_id(db, current_user, novel_id)
    ret_dict : Dict[int, List[schemas.RawChapterRevisionMeta]] = defaultdict(list)
    for chapter_num, raw_chapter_revision in result_rows:
        logger.info(chapter_num)
        logger.info(raw_chapter_revision)
        ret_dict[chapter_num].append(schemas.RawChapterRevisionMeta.model_validate(raw_chapter_revision.__dict__))
    return ret_dict

def insert_novel(
        db : Session, 
        current_user : User, 
        novel : schemas.CreateNovel
    ) -> models.Novel:
    """
    Insert a novel into the database.

    Args:
        db: Database which we are inserting into.
        current_user: User performing the insert. Exact user validation protocol has yet to be determined.
        novel: Metadata of novel.
    
    Raises:
        LanguageNotFoundException: Language id in request does not exist.
        DataTooLongException: String is too long in some field of data we are inserting.
        InsufficientPermissionsException: User does not have permission to create a novel
        UnknownError: Some other error occured.
    """
    db_novel = models.Novel(**novel.model_dump())
    try:
        db.add(db_novel)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
            raise LanguageNotFoundException(str(e.orig))
        raise UnknownError(e)
    except DataError as e:
        db.rollback()
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
            raise DataTooLongException(str(e.orig))
        raise UnknownError(e)
    except Exception as e:
        db.rollback()
        raise UnknownError(e)
    return db_novel

def modify_novel(
        db : Session, 
        current_user : User, 
        novel_id : int, 
        update : schemas.UpdateNovel
    ) -> models.Novel:
    """
    Modifies novel with novel_id.

    Args:
        db: Database containing the novel to modify.
        current_user: User performing the modify. Exact user validation protocol has yet to be determined.
        novel_id: id of novel to modify.
        update: Proposed updated metadata.
    
    Raises:
        NovelNotFoundException: Novel not found in database.
        NovelTooManyFoundException: Multiple novels with id found in database.
        DataTooLongException: Data we are updating to is too long for some string field.
        InsufficientPermissionsException: Current user does not have permission to update this resource.
    Todo:
        Make this function atomic.
    """
    db_novel = query_novel_by_id(db, current_user, novel_id)
    try:
        if update.novel_title is not None:
            db_novel.novel_title = update.novel_title 
        if update.novel_author is not None:
            db_novel.novel_author = update.novel_author
        if update.novel_description is not None:
            db_novel.novel_description = update.novel_description
        db.commit()
    except DataError as e:
        db.rollback()
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
            raise DataTooLongException(str(e.orig))
        raise UnknownError(e)
    except MultipleResultsFound as e:
        db.rollback()
        raise NovelTooManyFoundException
    except Exception as e:
        db.rollback()
        raise UnknownError(e)
    return db_novel

def insert_raw_chapter(
        db : Session, 
        current_user : User, 
        novel_id : int, 
        raw_chapter : schemas.CreateRawChapter
    ) -> models.RawChapter:
    """
    Insert a raw chapter into a database.

    Args:
        db: Database into which we are inserting the raw chapter.
        current_user: User performing the insert. 
        novel_id: id of novel the chapter belongs to
        raw_chapter: Data to insert.
    
    Raises:
        NovelIDNotFoundException: Novel with novel_id does not exist in db.
        ChapterNumDuplicateException: Chapter with chapter_num already exists in db.
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    new_chapter = models.RawChapter(**raw_chapter.model_dump(), novel_id=novel_id)
    try:
        db.add(new_chapter)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
            raise NovelNotFoundException(str(e.orig))
        if pgcode == errorcodes.UNIQUE_VIOLATION:
            raise ChapterNumDuplicateException(str(e.orig))
        raise UnknownError(e)
    except Exception as e:
        db.rollback()
        raise UnknownError(e)
    return new_chapter

def insert_raw_chapter_revision(
        db : Session, 
        current_user : User, 
        raw_chapter_id : int, 
        rcr : schemas.CreateRawChapterRevision
    ) -> models.RawChapterRevision:
    """
    Insert a raw chapter revision into the database.

    Args:
        db: Database into which we are adding the revision.
        current_user: User performing insert.
        raw_chapter_id: id of raw chapter this revision belongs to.
        rcr: Data to insert.
    
    Raises:
        RawChapterNotFoundException: Raw chapter with raw_chapter_id does not exist.
        DataTooLongException: String field we are trying to insert too long.
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    new_revision = models.RawChapterRevision(**rcr.model_dump(), raw_chapter_id=raw_chapter_id, raw_chapter_revision_is_primary=False, raw_chapter_revision_is_public=False, raw_chapter_revision_is_final=False)
    try:
        db.add(new_revision)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
            raise RawChapterNotFoundException(str(e.orig))
        raise UnknownError(e)
    except DataError as e:
        db.rollback()
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
            raise DataTooLongException(str(e.orig))
        raise UnknownError(e)
    except Exception as e:
        db.rollback()
        raise UnknownError(e)
    return new_revision

def modify_raw_chapter_revision(
        db : Session, 
        current_user : User,
        revision_id : int,
        rcr : schemas.UpdateRawChapterRevision, 
    ) -> models.RawChapterRevision:
    """
    Modifies data of raw chapter revision with revision_id. Cannot modify public revisions.

    Args:
        db: Database that contains the raw chapter revision to modify.
        current_user: User performing the update.
        revision_id: id of raw chapter revision we are modifying.

    Raises:
        RawChapterRevisionNotFoundException: raw_chapter_revision_id does not correspond to a raw chapter revision in db.
        DataTooLongException: String we are trying to modify is too long.
        InsufficientPermissionsException: User does not have permission to perform this operation.
        UnknownError: Some other error occured.
    """
    revision = query_raw_chapter_revision_by_id(db, current_user, revision_id)
    if revision.raw_chapter_revision_is_final:
        raise InsufficientPermissionsException # change this to something more descriptive later
    check_permissions(current_user)
    try:
        if rcr.raw_chapter_revision_title is not None:
            revision.raw_chapter_revision_title = rcr.raw_chapter_revision_title
        if rcr.raw_chapter_revision_text is not None:
            revision.raw_chapter_revision_text = rcr.raw_chapter_revision_text
        db.commit()
    except DataError as e:
        db.rollback()
        pgcode = e.orig.pgcode
        if pgcode == errorcodes.STRING_DATA_RIGHT_TRUNCATION:
            raise DataTooLongException(str(e.orig))
        raise UnknownError(e)
    except Exception as e:
        db.rollback()
        raise UnknownError(e)
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
        RawChapterRevisionNotFoundException: Raw chapter revision with raw_chapter_revision_id not found
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    revision = query_raw_chapter_revision_by_id(db, current_user, raw_chapter_revision_id)
    try:
        if not revision.raw_chapter_revision_is_public:
            revision.raw_chapter_revision_is_public = True
            db.commit()
    except Exception as e:
        db.rollback()
        raise UnknownError(e)
    return revision

def make_primary_raw_chapter_revision(db : Session, current_user : User, raw_chapter_revision_id : int) -> models.RawChapterRevision:
    """
    Mark a raw chapter revision as primary.

    Args:
        db: Database in which the data resides.
        current_user: User publishing the revision.
        raw_chapter_revision_id: id of the revision we are publishing.
    
    Raises:
        RawChapterRevisionNotFoundException: Raw chapter revision with raw_chapter_revision_id not found.
        RawChapterNotFound: Raw chapter corresponding to revision with raw_chapter_revision_id not found.
        RawChapterRevisionMakePrimaryFailedException: Failed during the db commit.
        RawChapterRevisionNotPublicException: Trying to make a non-public revision primary
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    revision = query_raw_chapter_revision_by_id(db, current_user, raw_chapter_revision_id)
    if not revision.raw_chapter_revision_is_public:
        raise RawChapterRevisionNotPublicException
    primaries = query_raw_chapter_revisions_by_raw_chapter(db, current_user, revision.raw_chapter_id, None, True)
    try:
        if len(primaries) == 0:
            revision.raw_chapter_revision_is_primary = True
            db.commit()
        elif len(primaries) > 1:
            raise UnknownError(f"Error: found more than one primary chapter for chapter with id {revision.raw_chapter_id}")
        else:
            current_primary = primaries[0]
            if current_primary != revision:
                current_primary.raw_chapter_revision_is_primary = False
                db.commit()
                revision.raw_chapter_revision_is_primary = True
                db.commit()
    except IntegrityError as e:
        if e.orig.pgcode == errorcodes.UNIQUE_VIOLATION:
            raise RawChapterRevisionMakePrimaryFailedException(f"Error: committing would violate a unique constraint. This is most likely caused by a race condition.")
        if e.orig.pgcode == errorcodes.CHECK_VIOLATION: # extra check
            raise RawChapterRevisionNotPublicException
    except UnknownError as e:
        raise e
    except Exception as e:
        db.rollback()
        raise UnknownError(str(e.orig))
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
        RawChapterRevisionNotFoundException: Raw chapter revision with raw_chapter_revision_id not found
        InsufficientPermissionsException: Current user does not have permissions to perform this action.
        UnknownError: Some other error occured.
    """
    revision = query_raw_chapter_revision_by_id(db, current_user, raw_chapter_revision_id)
    try:
        if not revision.raw_chapter_revision_is_final:
            revision.raw_chapter_revision_is_final = True
            db.commit()
    except Exception as e:
        db.rollback()
        raise UnknownError(e)
    return revision

def remove_raw_chapter_revision(
        db : Session, 
        current_user : User, 
        raw_chapter_revision_id : int, 
        force_remove : bool = False
    ) -> schemas.DeleteRawChapterRevisionStatus:
    """
    Remove a raw chapter revision from the database.

    Args:
        db: Database to remove from.
        current_user: User removing the chapter.
        raw_chapter_revision_id: id of revision to remove.
        force_remove: If True, and user validation succeeds, then remove this revision and everything it owns.
    
    Raises:
        RawChapterRevisionNotFoundException: Revision with raw_chapter_revision_id not found.
        InsufficientPermissionsException: Current user has insufficient permissions to delete this chapter.
        DeleteRawChapterFailedException: Delete failed for other reasons.
    """
    revision = query_raw_chapter_revision_by_id(db, current_user, raw_chapter_revision_id)
    check_permissions(current_user)
    try:
        if revision.raw_chapter_revision_is_final:
            if not force_remove:
                db.rollback()
                return schemas.DeleteRawChapterRevisionStatus(status="verify", detail="Verify that you want to delete this public chapter.", verify="")
            else:
                # implement delete cascade
                pass
        else:
            db.delete(revision)
            db.commit()
    except DeleteRawChapterRevisionFailedException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise DeleteRawChapterRevisionFailedException
    return schemas.DeleteRawChapterRevisionStatus(status="success", detail="Delete succeeded.")