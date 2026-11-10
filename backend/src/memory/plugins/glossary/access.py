from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, overload
from uuid import UUID

from sqlalchemy import SQLColumnExpression, func, insert, literal, or_, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, aliased

from src.memory.access import MemAccessContext, check_mem_access_ctx, write_memory
from src.memory.exceptions import (
    GlossaryTermAlreadyExistsException,
    GlossaryTermNotFoundException,
    MemoryNotFoundException,
)
from src.memory.models import Memory
from src.memory.overlay import visible_rows, workspace_read
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory, AgentGlossaryMemoryPage, AgentGlossaryTerm
from src.memory.plugins.glossary.types import TermKind
from src.memory.schemas import AgentMemory
from src.memory.shadow_models import ShadowGlossaryAssociation, ShadowMemory, ShadowTerm
from src.memory.staging import check_workspace, stage_record
from src.memory.types import Creator, MemoryType, PluginName, ReviewStatus, Scope
from src.novels.models import Chapter, ChapterContent
from src.schemas import Page

type ContainsQuery = Callable[
    [SQLColumnExpression[str], SQLColumnExpression[str]],
    SQLColumnExpression[bool],
]

GLOSSARY_PLUGIN_NAME: Final[PluginName] = "glossary"
# ``alias`` was the original, untyped mark.  Keep it in this set so existing
# memories remain useful, but only the dedicated alias writer may create new
# links and it always uses one of the typed marks below.
ALIAS_MARK: Final = "alias"
ALIAS_SPELLING_MARK: Final = "alias.spelling"
ALIAS_PERSONA_MARK: Final = "alias.persona"
ALIAS_TRANSFORMATION_MARK: Final = "alias.transformation"
ALIAS_MARKS: Final = (
    ALIAS_MARK,
    ALIAS_SPELLING_MARK,
    ALIAS_PERSONA_MARK,
    ALIAS_TRANSFORMATION_MARK,
)
MAX_ALIAS_TERMS: Final = 32
MAX_ALIAS_EDGES: Final = 64


TERM_NAME_MARKS: Final = "『』《》【】"


def strip_term_name_marks(term: SQLColumnExpression[str]) -> SQLColumnExpression[str]:
    return func.translate(term, TERM_NAME_MARKS, "")


def contains_query(chapter: SQLColumnExpression[str], term: SQLColumnExpression[str]) -> SQLColumnExpression[bool]:
    return func.strpos(chapter, term) > 0


def get_terms_in_chapter(
    db: Session,
    ctx: MemAccessContext,
    contains_query: ContainsQuery,
    *,
    include_rejected: bool = False,
) -> list[GlossaryTerm]:
    """Get glossary terms occurring in the exact chapter content pinned by the context."""
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, ctx.workspace_id)
    check_mem_access_ctx(db, ctx)
    query = (
        select(term_rows)
        .select_from(ChapterContent)
        .join(
            term_rows,
            contains_query(ChapterContent.chapter_content_text, term_rows.term),
        )
        .where(
            ChapterContent.chapter_content_id == ctx.chapter_content_id,
            ChapterContent.chapter_id == ctx.chapter_id,
            term_rows.memory_group_id == ctx.memory_group_id,
        )
        .order_by(term_rows.term, term_rows.term_id)
    )
    if not include_rejected:
        query = query.where(term_rows.review_status != ReviewStatus.REJECTED)
    return list(db.scalars(workspace_read(query, ctx.workspace_id)).all())


@dataclass(frozen=True)
class RangeTerm:
    term: GlossaryTerm
    first_chapter_num: int


def get_terms_in_chapter_range(
    db: Session,
    ctx: MemAccessContext,
    start_chapter_num: int | None,
    *,
    limit: int,
    include_rejected: bool = False,
) -> tuple[list[RangeTerm], bool]:
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, ctx.workspace_id)
    end_chapter_num, novel_id = check_mem_access_ctx(db, ctx)
    latest = (
        select(Chapter.chapter_num, ChapterContent.chapter_content_text)
        .join(ChapterContent, ChapterContent.chapter_id == Chapter.chapter_id)
        .where(Chapter.novel_id == novel_id, Chapter.chapter_num <= end_chapter_num)
        .ext(distinct_on(Chapter.chapter_id))
        .order_by(Chapter.chapter_id, ChapterContent.chapter_content_version.desc())
    )
    if start_chapter_num is not None:
        latest = latest.where(Chapter.chapter_num >= start_chapter_num)
    contents = latest.subquery()
    first_chapter_num = func.min(contents.c.chapter_num).label("first_chapter_num")
    statement = (
        select(term_rows, first_chapter_num)
        .join(contents, contains_query(contents.c.chapter_content_text, term_rows.term))
        .where(term_rows.memory_group_id == ctx.memory_group_id)
        .group_by(
            *(getattr(term_rows, column.name) for column in GlossaryTerm.__table__.columns)
            if ctx.workspace_id is not None
            else (term_rows.term_id,)
        )
        .order_by(first_chapter_num, term_rows.term)
    )
    if not include_rejected:
        statement = statement.where(term_rows.review_status != ReviewStatus.REJECTED)
    rows = [
        RangeTerm(term, first)
        for term, first in db.execute(workspace_read(statement.limit(limit + 1), ctx.workspace_id))
    ]
    return rows[:limit], len(rows) > limit


def inspect_terms(
    db: Session,
    ctx: MemAccessContext,
    term_names: list[str],
    memory_types: Sequence[MemoryType] | None,
    skip: int = 0,
    limit: int = 100,
    *,
    active_only: bool = True,
    include_rejected: bool = False,
    marks: Sequence[str | None] | None = None,
    term_search: str | None = None,
    expand_aliases: bool = False,
) -> Page[AgentGlossaryMemory[UUID]]:
    memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, ctx.workspace_id)
    association_rows = visible_rows(GlossaryAssociation, ShadowGlossaryAssociation, ctx.workspace_id)
    chap_num, _ = check_mem_access_ctx(db, ctx)
    alias_memories: list[Memory] = []
    aliases_truncated = False
    if expand_aliases:
        term_names, alias_memories, aliases_truncated = _expand_alias_terms(db, ctx, chap_num, term_names)

    matching_association = aliased(association_rows)
    matching_term = aliased(term_rows)
    matching_memory_ids = (
        select(matching_association.memory_id)
        .join(matching_term, matching_term.term_id == matching_association.term_id)
        .where(
            matching_term.term.in_(term_names),
            matching_term.memory_group_id == ctx.memory_group_id,
        )
        .distinct()
    )
    if not include_rejected:
        matching_memory_ids = matching_memory_ids.where(matching_term.review_status != ReviewStatus.REJECTED)

    def build_memory_query():
        query = select(memory_rows).where(
            memory_rows.memory_id.in_(matching_memory_ids),
            memory_rows.memory_group_id == ctx.memory_group_id,
            memory_rows.memory_start_num <= chap_num,
            memory_rows.plugin_name == GLOSSARY_PLUGIN_NAME,
        )
        if active_only:
            query = query.where(or_(memory_rows.memory_end_num.is_(None), memory_rows.memory_end_num > chap_num))
        if not include_rejected:
            query = query.where(memory_rows.memory_review_status != ReviewStatus.REJECTED)
        if memory_types is not None:
            query = query.where(memory_rows.memory_type.in_(memory_types))
        if marks is not None:
            non_null_marks = [mark for mark in marks if mark is not None]
            mark_filters = []
            if non_null_marks:
                mark_filters.append(memory_rows.mark.in_(non_null_marks))
            if None in marks:
                mark_filters.append(memory_rows.mark.is_(None))
            query = query.where(or_(*mark_filters) if mark_filters else memory_rows.mark.in_([]))
        if term_search is not None:
            query = query.where(memory_rows.memory_content.icontains(term_search, autoescape=True))
        return query

    count = (
        db.scalar(workspace_read(select(func.count()).select_from(build_memory_query().subquery()), ctx.workspace_id))
        or 0
    )
    memories = list(
        db.scalars(
            workspace_read(
                build_memory_query()
                .order_by(memory_rows.memory_start_num.desc(), memory_rows.memory_id)
                .offset(skip)
                .limit(limit),
                ctx.workspace_id,
            )
        ).all()
    )
    memory_ids = [memory.memory_id for memory in memories]
    terms_query = (
        select(association_rows.memory_id, term_rows)
        .select_from(association_rows)
        .join(term_rows, term_rows.term_id == association_rows.term_id)
        .where(
            association_rows.memory_id.in_(memory_ids),
            term_rows.memory_group_id == ctx.memory_group_id,
        )
        .order_by(association_rows.memory_id, term_rows.term, term_rows.term_id)
    )
    if not include_rejected:
        terms_query = terms_query.where(term_rows.review_status != ReviewStatus.REJECTED)

    terms_by_memory: dict[UUID, list[AgentGlossaryTerm]] = {memory_id: [] for memory_id in memory_ids}
    for memory_id, term in db.execute(workspace_read(terms_query, ctx.workspace_id)):
        terms_by_memory[memory_id].append(AgentGlossaryTerm.model_validate(term))
    rows = [
        AgentGlossaryMemory[UUID](
            memory=AgentMemory.model_validate(memory),
            terms=terms_by_memory[memory.memory_id],
        )
        for memory in memories
    ]
    if expand_aliases:
        return AgentGlossaryMemoryPage[UUID](
            count=count,
            rows=rows,
            aliases=_agent_glossary_memories(
                db, ctx.memory_group_id, alias_memories, include_rejected, ctx.workspace_id
            ),
            aliases_truncated=aliases_truncated,
        )
    return Page[AgentGlossaryMemory[UUID]](count=count, rows=rows)


def _agent_glossary_memories(
    db: Session,
    memory_group_id: UUID,
    memories: Sequence[Memory],
    include_rejected: bool,
    workspace_id: UUID | None = None,
) -> list[AgentGlossaryMemory[UUID]]:
    """Attach original term forms to an already ordered collection of memories."""
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, workspace_id)
    association_rows = visible_rows(GlossaryAssociation, ShadowGlossaryAssociation, workspace_id)
    memory_ids = [memory.memory_id for memory in memories]
    if not memory_ids:
        return []
    query = (
        select(association_rows.memory_id, term_rows)
        .select_from(association_rows)
        .join(term_rows, term_rows.term_id == association_rows.term_id)
        .where(association_rows.memory_id.in_(memory_ids), term_rows.memory_group_id == memory_group_id)
        .order_by(association_rows.memory_id, term_rows.term, term_rows.term_id)
    )
    if not include_rejected:
        query = query.where(term_rows.review_status != ReviewStatus.REJECTED)
    terms_by_memory: dict[UUID, list[AgentGlossaryTerm]] = {memory_id: [] for memory_id in memory_ids}
    for memory_id, term in db.execute(workspace_read(query, workspace_id)):
        terms_by_memory[memory_id].append(AgentGlossaryTerm.model_validate(term))
    return [
        AgentGlossaryMemory[UUID](memory=AgentMemory.model_validate(memory), terms=terms_by_memory[memory.memory_id])
        for memory in memories
    ]


def _expand_alias_terms(
    db: Session,
    ctx: MemAccessContext,
    chapter_num: int,
    term_names: Sequence[str],
) -> tuple[list[str], list[Memory], bool]:
    """Expand active pair aliases with bounded deterministic traversal.

    Legacy flat aliases remain readable alongside typed aliases. Records with
    more than two terms are deliberately ignored: they may describe a broad
    relation rather than pairwise identity equivalence.
    """
    memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, ctx.workspace_id)
    association_rows = visible_rows(GlossaryAssociation, ShadowGlossaryAssociation, ctx.workspace_id)
    initial_terms = list(
        db.scalars(
            workspace_read(
                select(term_rows.term)
                .where(
                    term_rows.memory_group_id == ctx.memory_group_id,
                    term_rows.term.in_(term_names),
                    term_rows.review_status != ReviewStatus.REJECTED,
                )
                .order_by(term_rows.term, term_rows.term_id),
                ctx.workspace_id,
            )
        ).all()
    )
    if not initial_terms:
        return list(term_names), [], False

    alias_rows = list(
        db.execute(
            workspace_read(
                select(memory_rows, term_rows)
                .select_from(memory_rows)
                .join(association_rows, association_rows.memory_id == memory_rows.memory_id)
                .join(term_rows, term_rows.term_id == association_rows.term_id)
                .where(
                    memory_rows.memory_group_id == ctx.memory_group_id,
                    memory_rows.plugin_name == GLOSSARY_PLUGIN_NAME,
                    memory_rows.memory_type == MemoryType.RELATION,
                    memory_rows.mark.in_(ALIAS_MARKS),
                    memory_rows.memory_review_status != ReviewStatus.REJECTED,
                    memory_rows.memory_start_num <= chapter_num,
                    or_(memory_rows.memory_end_num.is_(None), memory_rows.memory_end_num > chapter_num),
                    term_rows.memory_group_id == ctx.memory_group_id,
                )
                .order_by(
                    memory_rows.memory_start_num.desc(), memory_rows.memory_id, term_rows.term, term_rows.term_id
                ),
                ctx.workspace_id,
            )
        )
    )
    terms_by_alias: dict[UUID, list[GlossaryTerm]] = {}
    memories_by_id: dict[UUID, Memory] = {}
    for memory, term in alias_rows:
        memories_by_id[memory.memory_id] = memory
        terms_by_alias.setdefault(memory.memory_id, []).append(term)

    adjacency: dict[str, list[tuple[str, Memory]]] = {}
    for memory_id, terms in terms_by_alias.items():
        if len(terms) != 2 or any(term.review_status == ReviewStatus.REJECTED for term in terms):
            continue
        first, second = terms
        memory = memories_by_id[memory_id]
        adjacency.setdefault(first.term, []).append((second.term, memory))
        adjacency.setdefault(second.term, []).append((first.term, memory))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], -item[1].memory_start_num, str(item[1].memory_id)))

    reached = set(initial_terms)
    queue = list(initial_terms)
    used_edges: list[Memory] = []
    used_edge_ids: set[UUID] = set()
    truncated = False
    while queue:
        current = queue.pop(0)
        for other, memory in adjacency.get(current, []):
            if memory.memory_id in used_edge_ids:
                continue
            if len(used_edges) >= MAX_ALIAS_EDGES:
                truncated = True
                break
            if other not in reached and len(reached) >= MAX_ALIAS_TERMS:
                truncated = True
                continue
            used_edge_ids.add(memory.memory_id)
            used_edges.append(memory)
            if other not in reached:
                reached.add(other)
                queue.append(other)
        if truncated and len(used_edges) >= MAX_ALIAS_EDGES:
            break
    return sorted(reached), used_edges, truncated


@overload
def create_term(
    db: Session,
    memory_group_id: UUID,
    term_name: str,
    term_kind: TermKind | None = None,
    *,
    workspace_id: None = None,
) -> GlossaryTerm: ...


@overload
def create_term(
    db: Session,
    memory_group_id: UUID,
    term_name: str,
    term_kind: TermKind | None = None,
    *,
    workspace_id: UUID,
) -> ShadowTerm: ...


def create_term(
    db: Session,
    memory_group_id: UUID,
    term_name: str,
    term_kind: TermKind | None = None,
    *,
    workspace_id: UUID | None = None,
) -> GlossaryTerm | ShadowTerm:
    if workspace_id is not None:
        check_workspace(db, workspace_id, memory_group_id)
        term_rows = visible_rows(GlossaryTerm, ShadowTerm, workspace_id)
        if (
            db.scalar(
                select(term_rows.term_id).where(
                    term_rows.memory_group_id == memory_group_id, term_rows.term == term_name
                )
            )
            is not None
        ):
            raise GlossaryTermAlreadyExistsException(f"Glossary term {term_name!r} already exists")
        return stage_record(
            db, ShadowTerm, workspace_id, memory_group_id=memory_group_id, term=term_name, term_kind=term_kind
        )
    return db.execute(
        insert(GlossaryTerm)
        .values(memory_group_id=memory_group_id, term=term_name, term_kind=term_kind)
        .returning(GlossaryTerm)
    ).scalar_one()


def _set_term_review_status(
    db: Session,
    memory_group_id: UUID,
    term_id: UUID,
    review_status: ReviewStatus,
) -> GlossaryTerm:
    try:
        return db.execute(
            update(GlossaryTerm)
            .where(GlossaryTerm.term_id == term_id, GlossaryTerm.memory_group_id == memory_group_id)
            .values(review_status=review_status)
            .returning(GlossaryTerm)
        ).scalar_one()
    except NoResultFound as e:
        raise GlossaryTermNotFoundException(f"Glossary term with id {term_id} not found") from e


def approve_term(db: Session, memory_group_id: UUID, term_id: UUID) -> GlossaryTerm:
    return _set_term_review_status(db, memory_group_id, term_id, ReviewStatus.APPROVED)


def reject_term(db: Session, memory_group_id: UUID, term_id: UUID) -> GlossaryTerm:
    return _set_term_review_status(db, memory_group_id, term_id, ReviewStatus.REJECTED)


def mark_term_pending(db: Session, memory_group_id: UUID, term_id: UUID) -> GlossaryTerm:
    return _set_term_review_status(db, memory_group_id, term_id, ReviewStatus.PENDING)


def search_terms(
    db: Session,
    memory_group_id: UUID,
    query: str,
    *,
    limit: int,
    workspace_id: UUID | None = None,
    include_rejected: bool = False,
) -> tuple[int, list[GlossaryTerm]]:
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, workspace_id)
    needle = query.translate(str.maketrans("", "", TERM_NAME_MARKS))
    statement = select(term_rows).where(
        term_rows.memory_group_id == memory_group_id,
        strip_term_name_marks(term_rows.term).contains(needle, autoescape=True),
    )
    if not include_rejected:
        statement = statement.where(term_rows.review_status != ReviewStatus.REJECTED)
    count = db.scalar(workspace_read(select(func.count()).select_from(statement.subquery()), workspace_id)) or 0
    terms = list(
        db.scalars(workspace_read(statement.order_by(term_rows.term, term_rows.term_id).limit(limit), workspace_id))
    )
    return count, terms


def get_missing_term_names(
    db: Session, memory_group_id: UUID, term_names: list[str], *, workspace_id: UUID | None = None
) -> list[str]:
    """Return requested glossary terms that do not exist in the memory group."""
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, workspace_id)
    unique_term_names = list(dict.fromkeys(term_names))
    existing_term_names = set(
        db.scalars(
            workspace_read(
                select(term_rows.term).where(
                    term_rows.memory_group_id == memory_group_id,
                    term_rows.term.in_(unique_term_names),
                ),
                workspace_id,
            )
        ).all()
    )
    return [term_name for term_name in unique_term_names if term_name not in existing_term_names]


def _associate_terms(
    db: Session,
    memory_group_id: UUID,
    memory_id: UUID,
    term_names: list[str],
    *,
    workspace_id: UUID | None = None,
) -> list[GlossaryAssociation | ShadowGlossaryAssociation]:
    unique_term_names = list(dict.fromkeys(term_names))
    if not unique_term_names:
        return []
    if workspace_id is not None:
        term_rows = visible_rows(GlossaryTerm, ShadowTerm, workspace_id)
        term_ids = list(
            db.scalars(
                select(term_rows.term_id).where(
                    term_rows.term.in_(unique_term_names), term_rows.memory_group_id == memory_group_id
                )
            )
        )
        if len(term_ids) != len(unique_term_names):
            raise GlossaryTermNotFoundException("Some terms do not exist in the memory group.")
        return [
            stage_record(db, ShadowGlossaryAssociation, workspace_id, term_id=term_id, memory_id=memory_id)
            for term_id in term_ids
        ]
    association_source = select(
        GlossaryTerm.term_id,
        literal(memory_id),
    ).where(
        GlossaryTerm.term.in_(unique_term_names),
        GlossaryTerm.memory_group_id == memory_group_id,
    )
    associations = (
        db.execute(
            insert(GlossaryAssociation)
            .from_select(
                [GlossaryAssociation.term_id, GlossaryAssociation.memory_id],
                association_source,
            )
            .returning(GlossaryAssociation)
        )
        .scalars()
        .all()
    )
    if len(associations) != len(unique_term_names):
        raise GlossaryTermNotFoundException("Some terms do not exist in the memory group.")
    return list(associations)


def create_memory(
    db: Session,
    ctx: MemAccessContext,
    creator: Creator,
    mem_type: MemoryType,
    term_names: list[str],
    content: str,
    scope: Scope | None = None,
    mark: str | None = None,
) -> tuple[Memory | ShadowMemory, list[GlossaryAssociation | ShadowGlossaryAssociation]]:
    new_memory = write_memory(
        db,
        ctx,
        mem_type,
        content,
        creator,
        GLOSSARY_PLUGIN_NAME,
        scope,
        mark=mark,
    )
    glossary_associations = _associate_terms(
        db, ctx.memory_group_id, new_memory.memory_id, term_names, workspace_id=ctx.workspace_id
    )
    return new_memory, list(glossary_associations)


def supersede_memory(
    db: Session,
    ctx: MemAccessContext,
    memory_id: UUID,
    creator: Creator,
    mem_type: MemoryType,
    content: str,
    scope: Scope | None = None,
    mark: str | None = None,
    replacement_term_names: list[str] | None = None,
    expected_marks: Sequence[str | None] | None = None,
) -> tuple[Memory | ShadowMemory, list[GlossaryAssociation | ShadowGlossaryAssociation]]:
    if ctx.workspace_id is not None:
        check_mem_access_ctx(db, ctx)
    memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, ctx.workspace_id)
    association_rows = visible_rows(GlossaryAssociation, ShadowGlossaryAssociation, ctx.workspace_id)
    target_query = select(memory_rows.memory_id).where(
        memory_rows.memory_id == memory_id,
        memory_rows.memory_group_id == ctx.memory_group_id,
        memory_rows.plugin_name == GLOSSARY_PLUGIN_NAME,
        memory_rows.memory_type == mem_type,
    )
    if expected_marks is not None:
        non_null_marks = [expected_mark for expected_mark in expected_marks if expected_mark is not None]
        mark_filters = []
        if non_null_marks:
            mark_filters.append(memory_rows.mark.in_(non_null_marks))
        if None in expected_marks:
            mark_filters.append(memory_rows.mark.is_(None))
        target_query = target_query.where(or_(*mark_filters) if mark_filters else memory_rows.mark.in_([]))
    if db.scalar(target_query) is None:
        raise MemoryNotFoundException(f"Glossary memory with id {memory_id} is outside this toolset")

    if replacement_term_names is None:
        replacement_term_names = list(
            db.execute(
                select(term_rows.term)
                .select_from(association_rows)
                .where(association_rows.memory_id == memory_id)
                .join(term_rows, term_rows.term_id == association_rows.term_id)
                .where(
                    term_rows.memory_group_id == ctx.memory_group_id,
                )
            )
            .scalars()
            .all()
        )
    new_memory = write_memory(
        db,
        ctx,
        mem_type,
        content,
        creator,
        GLOSSARY_PLUGIN_NAME,
        scope,
        supersedes_id=memory_id,
        mark=mark,
    )
    new_assocs = _associate_terms(
        db, ctx.memory_group_id, new_memory.memory_id, replacement_term_names, workspace_id=ctx.workspace_id
    )
    return new_memory, new_assocs


def expire_memory(
    db: Session,
    ctx: MemAccessContext,
    memory_id: UUID,
    memory_types: Sequence[MemoryType],
    *,
    marks: Sequence[str | None] | None = None,
    end_offset: int = 0,
) -> None:
    """End an active glossary memory at the context chapter plus an internal offset."""
    chapter_num, _ = check_mem_access_ctx(db, ctx)
    end_num = chapter_num + end_offset
    memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
    try:
        conditions = [
            memory_rows.memory_id == memory_id,
            memory_rows.memory_group_id == ctx.memory_group_id,
            memory_rows.plugin_name == GLOSSARY_PLUGIN_NAME,
            memory_rows.memory_type.in_(memory_types),
            memory_rows.memory_start_num < end_num,
            or_(memory_rows.memory_end_num.is_(None), memory_rows.memory_end_num > chapter_num),
        ]
        if marks is not None:
            non_null_marks = [mark for mark in marks if mark is not None]
            mark_filters = []
            if non_null_marks:
                mark_filters.append(memory_rows.mark.in_(non_null_marks))
            if None in marks:
                mark_filters.append(memory_rows.mark.is_(None))
            conditions.append(or_(*mark_filters) if mark_filters else memory_rows.mark.in_([]))
        if ctx.workspace_id is not None:
            original = db.scalars(workspace_read(select(memory_rows).where(*conditions), ctx.workspace_id)).one()
            stage_record(db, ShadowMemory, ctx.workspace_id, original, memory_end_num=end_num)
        else:
            db.execute(
                update(Memory).where(*conditions).values(memory_end_num=end_num).returning(Memory.memory_id)
            ).scalar_one()
    except NoResultFound as exc:
        raise MemoryNotFoundException(f"Glossary memory with id {memory_id} not found or already ended") from exc


def read_agent_event_history(
    db: Session,
    ctx: MemAccessContext,
    subject_term_name: str,
    mark: str,
) -> tuple[int, list[Memory]]:
    memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, ctx.workspace_id)
    association_rows = visible_rows(GlossaryAssociation, ShadowGlossaryAssociation, ctx.workspace_id)
    chapter_num, _ = check_mem_access_ctx(db, ctx)
    memories = list(
        db.scalars(
            workspace_read(
                select(memory_rows)
                .join(association_rows, association_rows.memory_id == memory_rows.memory_id)
                .join(term_rows, term_rows.term_id == association_rows.term_id)
                .where(
                    term_rows.memory_group_id == ctx.memory_group_id,
                    term_rows.term == subject_term_name,
                    memory_rows.memory_group_id == ctx.memory_group_id,
                    memory_rows.plugin_name == GLOSSARY_PLUGIN_NAME,
                    memory_rows.memory_type == MemoryType.EVENT,
                    memory_rows.mark == mark,
                    memory_rows.creator_type == Creator.AGENT,
                    memory_rows.memory_review_status != ReviewStatus.REJECTED,
                    memory_rows.memory_start_num <= chapter_num,
                )
                .order_by(memory_rows.memory_start_num, memory_rows.memory_id),
                ctx.workspace_id,
            )
        ).all()
    )
    return chapter_num, memories


def can_supersede_agent_event(
    db: Session,
    ctx: MemAccessContext,
    memory_id: UUID,
    subject_term_name: str,
    mark: str,
) -> bool:
    memory_rows = visible_rows(Memory, ShadowMemory, ctx.workspace_id)
    term_rows = visible_rows(GlossaryTerm, ShadowTerm, ctx.workspace_id)
    association_rows = visible_rows(GlossaryAssociation, ShadowGlossaryAssociation, ctx.workspace_id)
    chapter_num, _ = check_mem_access_ctx(db, ctx)
    target_exists = db.scalar(
        workspace_read(
            select(memory_rows.memory_id)
            .join(association_rows, association_rows.memory_id == memory_rows.memory_id)
            .join(term_rows, term_rows.term_id == association_rows.term_id)
            .where(
                memory_rows.memory_id == memory_id,
                memory_rows.memory_group_id == ctx.memory_group_id,
                memory_rows.plugin_name == GLOSSARY_PLUGIN_NAME,
                memory_rows.memory_type == MemoryType.EVENT,
                memory_rows.mark == mark,
                memory_rows.creator_type == Creator.AGENT,
                memory_rows.memory_review_status != ReviewStatus.REJECTED,
                memory_rows.memory_start_num < chapter_num,
                or_(memory_rows.memory_end_num.is_(None), memory_rows.memory_end_num > chapter_num),
                term_rows.memory_group_id == ctx.memory_group_id,
                term_rows.term == subject_term_name,
            ),
            ctx.workspace_id,
        )
    )
    return target_exists is not None
