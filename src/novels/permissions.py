from sqlalchemy import select, or_, and_, exists, Select, Update, Delete

from .constants import *
from .models import *
from ..auth.models import User
from ..auth.constants import UserType


def novel_mod_access_select[T : Select](q : T, current_user : User | None) -> T:
    """
    Takes a select statement for novels and returns a select statement that restricts permissions on q.
    """
    if current_user is None:
        return q.where(Novel.novel_visibility >= Visibility.UNLISTED)
    elif current_user.user_type != UserType.ADMIN:
        return q.where(or_(
            Novel.novel_visibility >= Visibility.UNLISTED,
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == Novel.novel_id
                ).where(
                    Contributor.user_id == current_user.user_id
                )
            )
        ))
    return q

def raw_chapter_mod_access_select[T : Select](q : T, current_user : User | None) -> T:
    """
    Takes a select statement on raw chapters and returns a select statement that restricts permissions on raw chapters.
    """
    if current_user is None:
        return q.where(Novel.novel_visibility >= Visibility.UNLISTED)
    elif current_user.user_type != UserType.ADMIN:
        return q.where(or_(
            Novel.novel_visibility >= Visibility.UNLISTED,
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == Novel.novel_id
                ).where(
                    Contributor.user_id == current_user.user_id
                )
            )
        ))
    return q

def raw_chapter_revision_mod_access_select[T : Select](q : T,  current_user : User | None) -> T:
    """
    Takes a select statement on raw chapter revisions and returns a select statement that restricts permissions on raw chapter revisions.
    """
    if current_user is None:
        return novel_mod_access_select(q, None).where(RawChapterRevision.raw_chapter_revision_is_public == True)
    elif current_user.user_type != UserType.ADMIN:
        return q.where(or_(
            and_(
                Novel.novel_visibility >= Visibility.UNLISTED,
                RawChapterRevision.raw_chapter_revision_is_public == True
            ),
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(and_(
                    Contributor.novel_id == Novel.novel_id,
                    Contributor.user_id == current_user.user_id
                ))
            )
        ))
    return q

def novel_mod_access_update[T : Update](stmt : T, current_user : User) -> T:
    """
    Takes an update statement for novels and returns an update statement that restricts permissions on stmt.
    """
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == Novel.novel_id
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
                )
            )
        )
    return stmt

def raw_chapter_mod_access_insert[T : Select](stmt : T, current_user : User, novel_id : int) -> T:
    """
    Takes an select statement used for an insert from select statement for raw chapter and returns a select statement for a raw chapter that restrict permissions on stmt. 
    """
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == novel_id
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
                )
            )
        )
    return stmt

def raw_chapter_mod_access_update[T : Update](stmt : T, current_user : User) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == Novel.novel_id
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
                )
            )
        )
    return stmt

def raw_chapter_revision_mod_access_insert[T : Select](stmt : T, current_user : User, raw_chapter_id : int) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == select(
                        RawChapter.novel_id
                    ).where(
                        RawChapter.raw_chapter_id == raw_chapter_id
                    ).scalar_subquery()
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
                )
            )
        )
    return stmt

def raw_chapter_revision_mod_access_update[T : Update](stmt : T, current_user : User) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == select(
                        RawChapter.novel_id
                    ).where(
                        RawChapter.raw_chapter_id == RawChapterRevision.raw_chapter_id
                    ).scalar_subquery()
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
                )
            )
        )
    return stmt

def raw_chapter_revision_mod_access_delete[T : Delete](stmt : T, current_user : User) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == select(
                        RawChapter.novel_id
                    ).where(
                        RawChapter.raw_chapter_id == RawChapterRevision.raw_chapter_id
                    ).scalar_subquery()
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role == Role.OWNER
                )
            )
        )
    return stmt