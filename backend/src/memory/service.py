from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from src.auth.models import User
from src.languages.exceptions import LanguageNotFoundException
from src.languages.models import Language
from src.memory.exceptions import MemoryNotFoundException
from src.memory.models import Memory, MemoryGroup
from src.memory.permissions import (
    memory_group_mod_access_select,
    memory_mod_access_delete,
    memory_mod_access_select,
    memory_mod_access_update,
)
from src.memory.types import MemoryType, PluginName, ReviewStatus
from src.novels.exceptions import ChapterNotFoundException, NovelNotFoundException
from src.novels.models import Chapter, Novel
from src.novels.permissions import novel_mod_access_select


@dataclass(frozen=True)
class RowCount[T]:
    count: int
    rows: list[T]


def query_memory_groups(db: Session, user: User | None, novel_id: UUID):
    """Read all memory groups for a given novel."""
    query = select(MemoryGroup).where(MemoryGroup.novel_id == novel_id)
    query = memory_group_mod_access_select(query, user)
    return db.execute(query).scalars().all()


def create_memory_group(
    db: Session,
    user: User,
    memory_group_name: str,
    novel_id: UUID,
    memory_language: str,
) -> MemoryGroup:
    """Create a memory group for a novel the user may edit."""
    novel_query = select(Novel.novel_id).where(Novel.novel_id == novel_id)
    novel_query = novel_mod_access_select(novel_query, user, edit_only=True)
    if db.execute(novel_query).scalar_one_or_none() is None:
        raise NovelNotFoundException

    if db.get(Language, memory_language) is None:
        raise LanguageNotFoundException

    memory_group = MemoryGroup(
        memory_group_name=memory_group_name,
        novel_id=novel_id,
        memory_language=memory_language,
    )
    try:
        db.add(memory_group)
        db.commit()
        db.refresh(memory_group)
    except Exception:
        db.rollback()
        raise
    return memory_group


def query_memories_at_chapter(
    db: Session,
    user: User | None,
    memory_group_id: UUID,
    chapter_id: UUID,
    skip: int = 0,
    limit: int = 100,
    *,
    created_exactly_at_chapter: bool = False,
    plugin_names: list[PluginName] | None = None,
    memory_types: list[MemoryType] | None = None,
):
    """Read all memories in a memory group that are active at the given chapter."""
    try:
        chapter_query = (
            select(Chapter)
            .join(MemoryGroup, MemoryGroup.novel_id == Chapter.novel_id)
            .where(
                Chapter.chapter_id == chapter_id,
                MemoryGroup.memory_group_id == memory_group_id,
            )
        )
        chapter_query = memory_group_mod_access_select(chapter_query, user)
        chapter = db.execute(chapter_query).scalar_one()
    except NoResultFound as e:
        raise ChapterNotFoundException from e

    def build_query[T: Select[tuple[Any, ...]]](base: T):
        query = base.where(
            Memory.memory_group_id == memory_group_id,
            or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chapter.chapter_num),
        )
        query = memory_mod_access_select(query, user)
        if plugin_names is not None:
            query = query.where(Memory.plugin_name.in_(plugin_names))
        if memory_types is not None:
            query = query.where(Memory.memory_type.in_(memory_types))
        if created_exactly_at_chapter:
            query = query.where(Memory.memory_start_num == chapter.chapter_num)
        else:
            query = query.where(Memory.memory_start_num <= chapter.chapter_num)
        return query

    q1 = (
        build_query(select(Memory)).offset(skip).limit(limit).order_by(Memory.memory_start_num.desc(), Memory.memory_id)
    )
    q2 = build_query(select(func.count(Memory.memory_id)))

    return RowCount(count=db.execute(q2).scalar_one(), rows=list(db.execute(q1).scalars().all()))


def query_memories(
    db: Session,
    user: User | None,
    memory_group_id: UUID,
    skip: int = 0,
    limit: int = 100,
    *,
    plugin_names: list[PluginName] | None = None,
    memory_types: list[MemoryType] | None = None,
):
    """Read all memories in a memory group."""

    def build_query[T: Select[tuple[Any, ...]]](base: T):
        query = base.where(Memory.memory_group_id == memory_group_id)
        query = memory_mod_access_select(query, user)
        if plugin_names is not None:
            query = query.where(Memory.plugin_name.in_(plugin_names))
        if memory_types is not None:
            query = query.where(Memory.memory_type.in_(memory_types))
        return query

    return RowCount(
        count=db.execute(build_query(select(func.count(Memory.memory_id)))).scalar_one(),
        rows=list(
            db.execute(
                build_query(select(Memory))
                .offset(skip)
                .limit(limit)
                .order_by(Memory.memory_start_num.desc(), Memory.memory_id)
            )
            .scalars()
            .all()
        ),
    )


def query_one_memory(
    db: Session,
    user: User | None,
    memory_id: UUID,
):
    """Read a single memory by its ID."""
    query = select(Memory).where(Memory.memory_id == memory_id)
    query = memory_mod_access_select(query, user)
    try:
        return db.execute(query).scalar_one()
    except NoResultFound as e:
        raise MemoryNotFoundException from e


def change_review_status(
    db: Session,
    user: User,
    memory_id: UUID,
    new_review_status: ReviewStatus,
):
    """Change the review status of a memory."""
    query = (
        update(Memory)
        .where(Memory.memory_id == memory_id)
        .values(memory_review_status=new_review_status)
        .returning(Memory.memory_id)
    )
    query = memory_mod_access_update(query, user)
    try:
        updated_memory_id = db.execute(query).scalar_one()
        db.commit()
        return updated_memory_id
    except NoResultFound as e:
        db.rollback()
        raise MemoryNotFoundException from e
    except Exception:
        db.rollback()
        raise


def update_memory_content(
    db: Session,
    user: User,
    memory_id: UUID,
    new_content: str,
):
    """Update the content of a memory."""
    query = (
        update(Memory)
        .where(Memory.memory_id == memory_id)
        .values(memory_content=new_content)
        .returning(Memory.memory_id)
    )
    query = memory_mod_access_update(query, user)
    try:
        updated_memory_id = db.execute(query).scalar_one()
        db.commit()
        return updated_memory_id
    except NoResultFound as e:
        db.rollback()
        raise MemoryNotFoundException from e
    except Exception:
        db.rollback()
        raise


def expire_memory(
    db: Session,
    user: User,
    memory_id: UUID,
    chapter_id: UUID,
):
    """Expire an active memory at the start of a later chapter."""
    try:
        memory_query = (
            select(MemoryGroup.novel_id)
            .select_from(Memory)
            .join(MemoryGroup, MemoryGroup.memory_group_id == Memory.memory_group_id)
            .where(Memory.memory_id == memory_id)
        )
        memory_query = memory_mod_access_select(memory_query, user, edit_only=True)
        novel_id = db.execute(memory_query).scalar_one()
    except NoResultFound as e:
        raise MemoryNotFoundException from e

    try:
        chapter_num = db.execute(
            select(Chapter.chapter_num).where(Chapter.chapter_id == chapter_id, Chapter.novel_id == novel_id)
        ).scalar_one()
    except NoResultFound as e:
        raise ChapterNotFoundException from e

    query = (
        update(Memory)
        .where(
            Memory.memory_id == memory_id,
            Memory.memory_start_num < chapter_num,
            or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chapter_num),
        )
        .values(memory_end_num=chapter_num)
        .returning(Memory.memory_id)
    )
    query = memory_mod_access_update(query, user)
    try:
        expired_memory_id = db.execute(query).scalar_one()
        db.commit()
        return expired_memory_id
    except NoResultFound as e:
        db.rollback()
        raise MemoryNotFoundException from e
    except Exception:
        db.rollback()
        raise


def delete_memory(db: Session, user: User, memory_id: UUID):
    """Delete one memory and rely on plugin association cascades for cleanup."""
    query = delete(Memory).where(Memory.memory_id == memory_id).returning(Memory.memory_id)
    query = memory_mod_access_delete(query, user)
    try:
        deleted_memory_id = db.execute(query).scalar_one()
        db.commit()
        return deleted_memory_id
    except NoResultFound as e:
        db.rollback()
        raise MemoryNotFoundException from e
    except Exception:
        db.rollback()
        raise
