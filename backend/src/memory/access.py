from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import insert, or_, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from src.memory.exceptions import MemoryGroupNotFoundException, MemoryNotFoundException
from src.memory.models import Memory, MemoryGroup
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope
from src.novels.exceptions import ChapterContentNotFoundException
from src.novels.models import Chapter, ChapterContent, Novel

RECENT_SCOPE_LENGTH = 50
LOCAL_SCOPE_LENGTH = 1


@dataclass
class MemAccessContext:
    memory_group_id: UUID
    chapter_content_id: UUID


def check_mem_access_ctx(db: Session, ctx: MemAccessContext) -> tuple[int, UUID]:
    try:
        row = db.execute(
            select(Chapter.chapter_num, Novel.novel_id)
            .select_from(ChapterContent)
            .join(Chapter, ChapterContent.chapter_id == Chapter.chapter_id)
            .where(
                ChapterContent.chapter_content_id == ctx.chapter_content_id,
            )
            .join(Novel, Novel.novel_id == Chapter.novel_id)
        ).one()
    except NoResultFound as e:
        raise ChapterContentNotFoundException(f"Chapter content with id {ctx.chapter_content_id} not found") from e

    cur_chap_num, novel_id = row._t

    try:
        memory_group_novel_id = db.execute(
            select(MemoryGroup.novel_id).where(MemoryGroup.memory_group_id == ctx.memory_group_id)
        ).scalar_one()
    except NoResultFound as e:
        raise MemoryGroupNotFoundException(f"Memory group with id {ctx.memory_group_id} not found") from e

    if memory_group_novel_id != novel_id:
        raise ValueError(f"Memory group {ctx.memory_group_id} does not belong to novel {novel_id}")
    return cur_chap_num, novel_id


def _set_memory_review_status(
    db: Session,
    memory_group_id: UUID,
    memory_id: UUID,
    review_status: ReviewStatus,
) -> Memory:
    try:
        return db.execute(
            update(Memory)
            .where(Memory.memory_id == memory_id, Memory.memory_group_id == memory_group_id)
            .values(memory_review_status=review_status)
            .returning(Memory)
        ).scalar_one()
    except NoResultFound as e:
        raise MemoryNotFoundException(f"Memory with id {memory_id} not found") from e


def approve_memory(db: Session, memory_group_id: UUID, memory_id: UUID) -> Memory:
    return _set_memory_review_status(db, memory_group_id, memory_id, ReviewStatus.APPROVED)


def reject_memory(db: Session, memory_group_id: UUID, memory_id: UUID) -> Memory:
    return _set_memory_review_status(db, memory_group_id, memory_id, ReviewStatus.REJECTED)


def mark_memory_pending(db: Session, memory_group_id: UUID, memory_id: UUID) -> Memory:
    return _set_memory_review_status(db, memory_group_id, memory_id, ReviewStatus.PENDING)


def write_memory(
    db: Session,
    ctx: MemAccessContext,
    mem_type: MemoryType,
    content: str,
    creator_type: Creator,
    scope: Scope | None = None,
    supersedes_id: UUID | None = None,
) -> Memory:
    cur_chap_num, _ = check_mem_access_ctx(db, ctx)

    end = None
    if scope is None:
        if mem_type == MemoryType.EVENT:
            new_scope = Scope.RECENT
        else:
            new_scope = Scope.PERSIST
    else:
        new_scope = scope
    if new_scope == Scope.LOCAL:
        end = cur_chap_num + LOCAL_SCOPE_LENGTH
    elif new_scope == Scope.RECENT:
        end = cur_chap_num + RECENT_SCOPE_LENGTH

    if supersedes_id is not None:
        try:
            db.execute(
                update(Memory)
                .where(
                    Memory.memory_id == supersedes_id,
                    or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > cur_chap_num),
                    Memory.memory_start_num < cur_chap_num,
                    Memory.memory_group_id == ctx.memory_group_id,
                )
                .values(memory_end_num=cur_chap_num)
                .returning(Memory.memory_id)
            ).scalar_one()
        except NoResultFound as e:
            raise MemoryNotFoundException(f"Memory with id {supersedes_id} not found or already ended") from e
        except Exception as e:
            raise e
    new_memory = db.execute(
        insert(Memory)
        .values(
            memory_type=mem_type,
            memory_recorded_at=ctx.chapter_content_id,
            memory_start_num=cur_chap_num,
            memory_end_num=end,
            supersedes_memory_id=supersedes_id,
            memory_content=content,
            memory_group_id=ctx.memory_group_id,
            creator_type=creator_type,
        )
        .returning(Memory)
    ).scalar_one()
    return new_memory


def expire_memory(db: Session, ctx: MemAccessContext, memory_id: UUID) -> None:
    chap_num, _ = check_mem_access_ctx(db, ctx)
    try:
        db.execute(
            update(Memory)
            .where(
                Memory.memory_id == memory_id,
                or_(Memory.memory_end_num.is_(None), Memory.memory_end_num > chap_num),
                Memory.memory_start_num < chap_num,
                Memory.memory_group_id == ctx.memory_group_id,
            )
            .values(memory_end_num=chap_num)
            .returning(Memory.memory_id)
        ).scalar_one()
    except NoResultFound as e:
        raise MemoryNotFoundException(f"Memory with id {memory_id} not found or already ended") from e
    except Exception as e:
        raise e
