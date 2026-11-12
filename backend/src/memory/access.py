from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import SQLColumnExpression, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import ScalarSelect

from src.memory.exceptions import MemoryGroupNotFoundException, MemoryNotFoundException
from src.memory.models import Memory, MemoryGroup
from src.memory.overlay import visible_rows, workspace_read
from src.memory.shadow_models import ShadowMemory
from src.memory.staging import check_workspace, stage_record
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope
from src.novels.exceptions import ChapterContentNotFoundException
from src.novels.models import Chapter, ChapterContent, Novel

CONTINUITY_PLUGIN_NAME = "continuity"
RECENT_SCOPE_LENGTH = 15
LOCAL_SCOPE_LENGTH = 1


@dataclass(frozen=True)
class MemAccessContext:
    memory_group_id: UUID
    chapter_id: UUID
    chapter_content_id: UUID
    workspace_id: UUID | None = None


def check_mem_access_ctx(db: Session, ctx: MemAccessContext) -> tuple[int, UUID]:
    try:
        row = db.execute(
            select(Chapter.chapter_id, Chapter.chapter_num, Novel.novel_id)
            .select_from(ChapterContent)
            .join(Chapter, Chapter.chapter_id == ChapterContent.chapter_id)
            .join(Novel, Novel.novel_id == Chapter.novel_id)
            .where(ChapterContent.chapter_content_id == ctx.chapter_content_id)
        ).one()
    except NoResultFound as e:
        raise ChapterContentNotFoundException(f"Chapter content with id {ctx.chapter_content_id} not found") from e

    chapter_id, cur_chap_num, novel_id = row

    if chapter_id != ctx.chapter_id:
        raise ValueError(f"Chapter content {ctx.chapter_content_id} does not belong to chapter {ctx.chapter_id}")

    try:
        memory_group_novel_id = db.execute(
            select(MemoryGroup.novel_id).where(MemoryGroup.memory_group_id == ctx.memory_group_id)
        ).scalar_one()
    except NoResultFound as e:
        raise MemoryGroupNotFoundException(f"Memory group with id {ctx.memory_group_id} not found") from e

    if memory_group_novel_id != novel_id:
        raise ValueError(f"Memory group {ctx.memory_group_id} does not belong to novel {novel_id}")
    if ctx.workspace_id is not None:
        check_workspace(db, ctx.workspace_id, ctx.memory_group_id, ctx.chapter_id)
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
    plugin_name: str,
    scope: Scope | None = None,
    supersedes_id: UUID | None = None,
    *,
    mark: str | None = None,
) -> Memory | ShadowMemory:
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
        memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
        conditions = (
            memory_rows.memory_id == supersedes_id,
            or_(memory_rows.memory_end_num.is_(None), memory_rows.memory_end_num > cur_chap_num),
            memory_rows.memory_start_num < cur_chap_num,
            memory_rows.memory_group_id == ctx.memory_group_id,
            memory_rows.plugin_name == plugin_name,
        )
        try:
            if ctx.workspace_id is not None:
                original = db.scalars(workspace_read(select(memory_rows).where(*conditions), ctx.workspace_id)).one()
                stage_record(db, ShadowMemory, ctx.workspace_id, original, memory_end_num=cur_chap_num)
            else:
                db.execute(
                    update(Memory).where(*conditions).values(memory_end_num=cur_chap_num).returning(Memory.memory_id)
                ).scalar_one()
        except NoResultFound as e:
            raise MemoryNotFoundException(f"Memory with id {supersedes_id} not found or already ended") from e
    if ctx.workspace_id is not None:
        return stage_record(
            db,
            ShadowMemory,
            ctx.workspace_id,
            memory_type=mem_type,
            mark=mark,
            memory_observed_in=ctx.chapter_content_id,
            memory_start_num=cur_chap_num,
            memory_end_num=end,
            supersedes_memory_id=supersedes_id,
            memory_content=content,
            memory_group_id=ctx.memory_group_id,
            creator_type=creator_type,
            plugin_name=plugin_name,
        )
    new_memory = db.execute(
        insert(Memory)
        .values(
            memory_type=mem_type,
            mark=mark,
            memory_observed_in=ctx.chapter_content_id,
            memory_start_num=cur_chap_num,
            memory_end_num=end,
            supersedes_memory_id=supersedes_id,
            memory_content=content,
            memory_group_id=ctx.memory_group_id,
            creator_type=creator_type,
            plugin_name=plugin_name,
        )
        .returning(Memory)
    ).scalar_one()
    return new_memory


def expire_memory(db: Session, ctx: MemAccessContext, memory_id: UUID) -> None:
    chap_num, _ = check_mem_access_ctx(db, ctx)
    memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
    conditions = (
        memory_rows.memory_id == memory_id,
        or_(memory_rows.memory_end_num.is_(None), memory_rows.memory_end_num > chap_num),
        memory_rows.memory_start_num < chap_num,
        memory_rows.memory_group_id == ctx.memory_group_id,
    )
    try:
        if ctx.workspace_id is not None:
            original = db.scalars(workspace_read(select(memory_rows).where(*conditions), ctx.workspace_id)).one()
            stage_record(db, ShadowMemory, ctx.workspace_id, original, memory_end_num=chap_num)
        else:
            db.execute(
                update(Memory).where(*conditions).values(memory_end_num=chap_num).returning(Memory.memory_id)
            ).scalar_one()
    except NoResultFound as e:
        raise MemoryNotFoundException(f"Memory with id {memory_id} not found or already ended") from e


def _latest_content_id(chapter_id: SQLColumnExpression[UUID]) -> ScalarSelect[UUID]:
    latest_version = (
        select(ChapterContent.chapter_content_version)
        .where(ChapterContent.chapter_id == chapter_id)
        .order_by(ChapterContent.chapter_content_version.desc())
        .limit(1)
        .scalar_subquery()
    )
    return (
        select(ChapterContent.chapter_content_id)
        .where(
            ChapterContent.chapter_id == chapter_id,
            ChapterContent.chapter_content_version == latest_version,
        )
        .scalar_subquery()
    )


def read_previous_continuity_summary(db: Session, ctx: MemAccessContext) -> str | None:
    memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
    current_num, novel_id = check_mem_access_ctx(db, ctx)
    previous_chapter_id = (
        select(Chapter.chapter_id)
        .where(Chapter.novel_id == novel_id, Chapter.chapter_num < current_num)
        .order_by(Chapter.chapter_num.desc(), Chapter.chapter_id.desc())
        .limit(1)
        .scalar_subquery()
    )
    summary = db.scalar(
        workspace_read(
            select(memory_rows.memory_content)
            .where(
                memory_rows.memory_group_id == ctx.memory_group_id,
                memory_rows.memory_type == MemoryType.SUMMARY,
                memory_rows.plugin_name == CONTINUITY_PLUGIN_NAME,
                memory_rows.memory_observed_in == _latest_content_id(previous_chapter_id),
                memory_rows.memory_start_num <= current_num,
                or_(memory_rows.memory_end_num.is_(None), memory_rows.memory_end_num > current_num),
                memory_rows.memory_review_status != ReviewStatus.REJECTED,
            )
            .limit(1),
            ctx.workspace_id,
        )
    )
    # Human-authored legacy rows can bypass the structured output schema. Do
    # not truncate them into a different claim; omit them from agent context.
    return summary if summary is not None and len(summary) <= 1500 else None


def write_continuity_summary(db: Session, ctx: MemAccessContext, summary: str) -> None:
    chapter_num, _ = check_mem_access_ctx(db, ctx)
    if ctx.workspace_id is not None:
        memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
        original = db.scalar(
            workspace_read(
                select(memory_rows).where(
                    memory_rows.memory_group_id == ctx.memory_group_id,
                    memory_rows.memory_type == MemoryType.SUMMARY,
                    memory_rows.plugin_name == CONTINUITY_PLUGIN_NAME,
                    memory_rows.memory_observed_in == ctx.chapter_content_id,
                ),
                ctx.workspace_id,
            )
        )
        if original is not None:
            if original.creator_type == Creator.AGENT and original.memory_review_status == ReviewStatus.PENDING:
                stage_record(db, ShadowMemory, ctx.workspace_id, original, memory_content=summary)
        else:
            stage_record(
                db,
                ShadowMemory,
                ctx.workspace_id,
                memory_group_id=ctx.memory_group_id,
                memory_type=MemoryType.SUMMARY,
                memory_observed_in=ctx.chapter_content_id,
                memory_start_num=chapter_num,
                memory_content=summary,
                creator_type=Creator.AGENT,
                plugin_name=CONTINUITY_PLUGIN_NAME,
            )
        return
    stmt = pg_insert(Memory).values(
        memory_group_id=ctx.memory_group_id,
        memory_type=MemoryType.SUMMARY,
        memory_observed_in=ctx.chapter_content_id,
        memory_start_num=chapter_num,
        memory_content=summary,
        creator_type=Creator.AGENT,
        plugin_name=CONTINUITY_PLUGIN_NAME,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Memory.memory_group_id, Memory.memory_observed_in],
        index_where=(Memory.memory_type == MemoryType.SUMMARY) & (Memory.plugin_name == CONTINUITY_PLUGIN_NAME),
        set_={"memory_content": stmt.excluded.memory_content, "updated_at": func.now()},
        where=(Memory.creator_type == Creator.AGENT) & (Memory.memory_review_status == ReviewStatus.PENDING),
    )
    db.execute(stmt)
