import uuid
from typing import Any

from sqlalchemy import Delete, Select, Update, and_, exists, or_, select

from ..auth.constants import UserType
from ..auth.models import User
from .constants import Role, Visibility
from .models import Chapter, Contributor, Novel, Revision, RevisionText


def novel_mod_access_select[T : Select[tuple[Any, ...]]](q : T, current_user : User | None) -> T:
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

def chapter_mod_access_select[T : Select[tuple[Any, ...]]](q : T, current_user : User | None) -> T:
    """
    Takes a select statement on chapters and returns a select statement that restricts permissions on chapters.
    """
    if current_user is None:
        return q.where(Novel.novel_visibility >= Visibility.UNLISTED)
    elif current_user.user_type != UserType.ADMIN:
        sub_q = select(
            1
        ).select_from(Chapter).join(
            Novel, Chapter.novel_id == Novel.novel_id
        ).correlate(Chapter)
        sub_q = novel_mod_access_select(sub_q, current_user)
        return q.where(exists(sub_q))
    return q

def revision_mod_access_select[T : Select[tuple[Any, ...]]](q : T,  current_user : User | None) -> T:
    """
    Takes a select statement on revisions and returns a select statement that restricts permissions on revisions.
    """
    if current_user is None:
        sub_q = select(
            1
        ).select_from(Revision).where(
            Revision.revision_is_public.is_(True)
        ).join(
            Chapter,
            Revision.chapter_id == Chapter.chapter_id
        ).join(
            Novel,
            Chapter.novel_id == Novel.novel_id
        ).correlate(Revision)
        sub_q = novel_mod_access_select(sub_q, None)
        return q.where(exists(sub_q))
    elif current_user.user_type != UserType.ADMIN:
        sub_q = select(
            1
        ).select_from(Revision).join(
            Chapter,
            Revision.chapter_id == Chapter.chapter_id
        ).join(
            Novel,
            Chapter.novel_id == Novel.novel_id
        ).where(
            or_(
                and_(
                    Novel.novel_visibility >= Visibility.UNLISTED,
                    Revision.revision_is_public.is_(True)
                ),
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
            )
        ).correlate(Revision)
        return q.where(exists(sub_q))
    return q

def revision_text_mod_access_select[T : Select[tuple[Any, ...]]](q : T, current_user : User | None) -> T:
    subq = select(1).select_from(Revision).where(
        Revision.revision_id == RevisionText.revision_id
    ).correlate(RevisionText)
    subq = revision_mod_access_select(subq, current_user)
    return q.where(exists(subq))

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

def chapter_mod_access_insert[T : Select[tuple[Any, ...]]](stmt : T, current_user : User, novel_id : uuid.UUID) -> T:
    """
    Takes an select statement used for an insert from select statement for chapter and returns a select statement for a chapter that restrict permissions on stmt.
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

def chapter_mod_access_update[T : Update](stmt : T, current_user : User) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == Chapter.novel_id
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
                )
            )
        )
    return stmt

def revision_mod_access_insert[T : Select[tuple[Any, ...]]](stmt : T, current_user : User, chapter_id : uuid.UUID) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == select(
                        Chapter.novel_id
                    ).where(
                        Chapter.chapter_id == chapter_id
                    ).scalar_subquery()
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
                )
            )
        )
    return stmt

def revision_mod_access_update[T : Update](stmt : T, current_user : User) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == select(
                        Chapter.novel_id
                    ).where(
                        Chapter.chapter_id == Revision.chapter_id
                    ).scalar_subquery()
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
                )
            )
        )
    return stmt

def revision_mod_access_delete[T : Delete](stmt : T, current_user : User) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(
                    1
                ).select_from(
                    Contributor
                ).where(
                    Contributor.novel_id == select(
                        Chapter.novel_id
                    ).where(
                        Chapter.chapter_id == Revision.chapter_id
                    ).scalar_subquery()
                ).where(
                    Contributor.user_id == current_user.user_id
                ).where(
                    Contributor.contributor_role == Role.OWNER
                )
            )
        )
    return stmt

def revision_text_mod_access_insert[T : Select[tuple[Any, ...]]](stmt : T, current_user : User, revision_id : uuid.UUID) -> T:
    subq = select(1).select_from(Revision).where(
        Revision.revision_id == revision_id
    )
    subq = revision_mod_access_select(subq, current_user)
    return stmt.where(exists(subq))
