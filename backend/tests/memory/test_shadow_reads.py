from typing import Any

from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.access import MemAccessContext, read_previous_continuity_summary, write_continuity_summary
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.conventions.context import conventions_context
from src.memory.agent.toolsets.conventions.tools import search_glossary_terms
from src.memory.agent.toolsets.translations.tools import term_translation_context
from src.memory.models import Memory
from src.memory.plugins.conventions.access import create_convention, read_conventions
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.glossary.schemas import AgentGlossaryMemoryPage
from src.memory.plugins.glossary.types import TermKind
from src.memory.plugins.translations.access import missing_term_translations, read_term_translations
from src.memory.plugins.translations.models import TermTranslation
from src.memory.shadow_models import (
    ShadowConvention,
    ShadowGlossaryAssociation,
    ShadowMemory,
    ShadowTerm,
    ShadowTermTranslation,
)
from src.memory.types import Creator, MemoryType, ReviewStatus, Scope
from src.models import Base
from tests.fixtures.memory_workspaces import ReadScenario
from tests.fixtures.memory_workspaces import reads as reads


async def _stage[T: Base](db: AsyncSession, model: type[T], ctx: MemAccessContext, original: Base, **changes: Any) -> T:
    payload = {column.name: getattr(original, column.name) for column in inspect(type(original)).columns}
    payload.update(changes)
    row = model(workspace_id=ctx.workspace_id, **payload)
    db.add(row)
    await db.flush()
    return row


async def _draft_term(db: AsyncSession, ctx: MemAccessContext, name: str) -> ShadowTerm:
    row = ShadowTerm(workspace_id=ctx.workspace_id, memory_group_id=ctx.memory_group_id, term=name)
    db.add(row)
    await db.flush()
    return row


async def _draft_memory(
    db: AsyncSession,
    ctx: MemAccessContext,
    term: GlossaryTerm | ShadowTerm,
    content: str,
    *,
    kind: MemoryType = MemoryType.FACT,
    mark: str | None = None,
) -> ShadowMemory:
    row = ShadowMemory(
        workspace_id=ctx.workspace_id,
        memory_group_id=ctx.memory_group_id,
        memory_type=kind,
        memory_observed_in=ctx.chapter_content_id,
        memory_start_num=2,
        memory_content=content,
        creator_type=Creator.AGENT,
        plugin_name="glossary",
        mark=mark,
    )
    db.add(row)
    await db.flush()
    db.add(ShadowGlossaryAssociation(workspace_id=ctx.workspace_id, term_id=term.term_id, memory_id=row.memory_id))
    await db.flush()
    return row


async def test_term_overlays_isolate_cached_published_rows_and_refresh_drafts(
    async_test_db: AsyncSession, reads: ReadScenario
):
    alpha = await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha", TermKind.PERSON)
    beta = await access.create_term(async_test_db, reads.published.memory_group_id, "Beta")
    staged = await _stage(async_test_db, ShadowTerm, reads.current, alpha, term="Gamma")
    await _stage(async_test_db, ShadowTerm, reads.current, beta, deleted=True)
    await _draft_term(async_test_db, reads.current, "Zeta")

    async def names(ctx: MemAccessContext) -> list[str]:
        return [row.term for row in await access.get_terms_in_chapter(async_test_db, ctx, access.contains_query)]

    assert await names(reads.published) == await names(reads.other) == ["Alpha", "Beta"]
    assert await names(reads.current) == ["Gamma", "Zeta"]
    assert (alpha.term, beta.term) == ("Alpha", "Beta")
    assert await access.search_terms(
        async_test_db, reads.current.memory_group_id, "Alpha", limit=10, workspace_id=reads.current.workspace_id
    ) == (0, [])
    assert await access.get_missing_term_names(
        async_test_db,
        reads.current.memory_group_id,
        ["Alpha", "Gamma", "Beta", "Zeta"],
        workspace_id=reads.current.workspace_id,
    ) == ["Alpha", "Beta"]
    staged.term = "Delta"
    await async_test_db.flush()
    assert await names(reads.current) == ["Delta", "Zeta"]
    assert await names(reads.published) == ["Alpha", "Beta"]
    staged.review_status = ReviewStatus.REJECTED
    await async_test_db.flush()
    assert await names(reads.current) == ["Zeta"]
    rows, truncated = await access.get_terms_in_chapter_range(
        async_test_db, reads.current, 1, limit=1, include_rejected=True
    )
    assert [(row.term.term, row.first_chapter_num) for row in rows] == [("Delta", 1)]
    assert truncated


async def test_memory_filters_counts_and_pages_apply_after_overrides(async_test_db: AsyncSession, reads: ReadScenario):
    alpha = await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    originals = [
        (await access.create_memory(async_test_db, reads.published, Creator.AGENT, MemoryType.FACT, ["Alpha"], text))[0]
        for text in ["Changed type", "Deleted", "Ended", "Rejected"]
    ]
    await _stage(async_test_db, ShadowMemory, reads.current, originals[0], memory_type=MemoryType.EVENT)
    await _stage(async_test_db, ShadowMemory, reads.current, originals[1], deleted=True)
    await _stage(async_test_db, ShadowMemory, reads.current, originals[2], memory_start_num=1, memory_end_num=2)
    await _stage(async_test_db, ShadowMemory, reads.current, originals[3], memory_review_status=ReviewStatus.REJECTED)
    first = await _draft_memory(async_test_db, reads.current, alpha, "Draft first")
    second = await _draft_memory(async_test_db, reads.current, alpha, "Draft second")
    expected_ids = sorted([first.memory_id, second.memory_id])
    for skip in range(2):
        page = await access.inspect_terms(
            async_test_db, reads.current, ["Alpha"], [MemoryType.FACT], skip=skip, limit=1
        )
        assert page.count == 2
        assert [item.memory.memory_id for item in page.rows] == expected_ids[skip : skip + 1]
    assert (await access.inspect_terms(async_test_db, reads.published, ["Alpha"], [MemoryType.FACT])).count == 4
    assert (await access.inspect_terms(async_test_db, reads.other, ["Alpha"], [MemoryType.FACT])).count == 4
    assert (
        await access.inspect_terms(async_test_db, reads.current, ["Alpha"], [MemoryType.FACT], term_search="second")
    ).count == 1
    assert (
        await access.inspect_terms(async_test_db, reads.current, ["Alpha"], [MemoryType.FACT], active_only=False)
    ).count == 3
    assert (
        await access.inspect_terms(async_test_db, reads.current, ["Alpha"], [MemoryType.FACT], include_rejected=True)
    ).count == 3


async def test_association_overlays_match_both_key_columns_and_unpublished_endpoints(
    async_test_db: AsyncSession, reads: ReadScenario
):
    alpha = await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    await access.create_term(async_test_db, reads.published.memory_group_id, "Beta")
    memory, associations = await access.create_memory(
        async_test_db, reads.published, Creator.AGENT, MemoryType.FACT, ["Alpha", "Beta"], "Shared fact"
    )
    alpha_association = next(row for row in associations if row.term_id == alpha.term_id)
    await _stage(async_test_db, ShadowGlossaryAssociation, reads.current, alpha_association, deleted=True)
    gamma = await _draft_term(async_test_db, reads.current, "Gamma")
    async_test_db.add(
        ShadowGlossaryAssociation(
            workspace_id=reads.current.workspace_id, term_id=gamma.term_id, memory_id=memory.memory_id
        )
    )
    await async_test_db.flush()
    assert (await access.inspect_terms(async_test_db, reads.current, ["Alpha"], None)).count == 0
    page = await access.inspect_terms(async_test_db, reads.current, ["Beta", "Gamma"], None)
    assert page.count == 1
    assert [row.term for row in page.rows[0].terms] == ["Beta", "Gamma"]
    assert (await access.inspect_terms(async_test_db, reads.published, ["Alpha"], None)).count == 1


async def test_alias_expansion_uses_shadow_terms_memories_and_associations(
    async_test_db: AsyncSession, reads: ReadScenario
):
    alpha = await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    beta = await _draft_term(async_test_db, reads.current, "Beta")
    alias = await _draft_memory(
        async_test_db,
        reads.current,
        alpha,
        "Alpha is also Beta.",
        kind=MemoryType.RELATION,
        mark=access.ALIAS_PERSONA_MARK,
    )
    async_test_db.add(
        ShadowGlossaryAssociation(
            workspace_id=reads.current.workspace_id, term_id=beta.term_id, memory_id=alias.memory_id
        )
    )
    definition = await _draft_memory(async_test_db, reads.current, beta, "Beta definition.", kind=MemoryType.DEFINITION)
    page = await access.inspect_terms(
        async_test_db, reads.current, ["Alpha"], [MemoryType.DEFINITION], expand_aliases=True
    )
    assert isinstance(page, AgentGlossaryMemoryPage)
    assert [item.memory.memory_id for item in page.rows] == [definition.memory_id]
    assert [[term.term for term in item.terms] for item in page.aliases] == [["Alpha", "Beta"]]
    alias.deleted = True
    await async_test_db.flush()
    assert (
        await access.inspect_terms(
            async_test_db, reads.current, ["Alpha"], [MemoryType.DEFINITION], expand_aliases=True
        )
    ).count == 0


async def test_translation_overlays_mask_rejected_deleted_and_renamed_rows(
    async_test_db: AsyncSession, reads: ReadScenario
):
    alpha = await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    published = TermTranslation(term_id=alpha.term_id, translation="Published", creator_type=Creator.USER)
    async_test_db.add(published)
    await async_test_db.flush()
    staged = await _stage(async_test_db, ShadowTermTranslation, reads.current, published, translation="Draft")
    beta = await _draft_term(async_test_db, reads.current, "Beta")
    async_test_db.add(
        ShadowTermTranslation(
            workspace_id=reads.current.workspace_id,
            term_id=beta.term_id,
            translation="New name",
            creator_type=Creator.AGENT,
        )
    )
    await async_test_db.flush()
    assert [
        (row.term, row.translation)
        for row in await read_term_translations(async_test_db, reads.current, ["Alpha", "Beta"])
    ] == [("Alpha", "Draft"), ("Beta", "New name")]
    assert [
        (row.term, row.translation)
        for row in await read_term_translations(async_test_db, reads.other, ["Alpha", "Beta"])
    ] == [("Alpha", "Published")]
    staged.review_status = ReviewStatus.REJECTED
    await async_test_db.flush()
    assert await missing_term_translations(async_test_db, reads.current, ["Alpha", "Beta", "Alpha"]) == ["Alpha"]
    staged.review_status = ReviewStatus.PENDING
    staged.deleted = True
    await async_test_db.flush()
    assert await read_term_translations(async_test_db, reads.current, ["Alpha"]) == []
    staged.deleted = False
    await _stage(async_test_db, ShadowTerm, reads.current, alpha, term="Gamma")
    assert await read_term_translations(async_test_db, reads.current, ["Alpha"]) == []
    assert (await read_term_translations(async_test_db, reads.current, ["Gamma"]))[0].translation == "Draft"
    assert published.translation == "Published"


async def test_convention_filters_and_agent_contexts_read_the_workspace(
    async_test_db: AsyncSession, reads: ReadScenario
):
    alpha = await _draft_term(async_test_db, reads.current, "Alpha")
    await _draft_memory(async_test_db, reads.current, alpha, "A staged definition.", kind=MemoryType.DEFINITION)
    originals = [
        await create_convention(
            async_test_db,
            reads.published.memory_group_id,
            category=ConventionCategory.NAMING,
            title=title,
            rule="Published rule.",
            rationale=None,
            creator_type=Creator.AGENT,
        )
        for title in ["Changed category", "Deleted"]
    ]
    await _stage(async_test_db, ShadowConvention, reads.current, originals[0], category=ConventionCategory.STYLE)
    await _stage(async_test_db, ShadowConvention, reads.current, originals[1], deleted=True)
    draft = ShadowConvention(
        workspace_id=reads.current.workspace_id,
        memory_group_id=reads.current.memory_group_id,
        category=ConventionCategory.NAMING,
        title="Draft policy",
        rule="Draft rule.",
        creator_type=Creator.AGENT,
    )
    async_test_db.add(draft)
    await async_test_db.flush()
    assert [
        row.title
        for row in await read_conventions(
            async_test_db,
            reads.current.memory_group_id,
            workspace_id=reads.current.workspace_id,
            category=ConventionCategory.NAMING,
        )
    ] == ["Draft policy"]
    assert (
        len(await read_conventions(async_test_db, reads.published.memory_group_id, category=ConventionCategory.NAMING))
        == 2
    )
    naming = await term_translation_context(async_test_db, reads.current, include_conventions=True)
    assert naming is not None and [term.term for term in naming.requested_terms] == ["Alpha"]
    assert naming.conventions is not None and [row.title for row in naming.conventions] == ["Draft policy"]
    context = await conventions_context(MemAgentDeps(async_test_db, reads.current), 1)
    assert [term.definition for term in context.terms] == ["A staged definition."]
    assert {row.title for row in context.conventions} == {"Changed category", "Draft policy"}
    search = await search_glossary_terms(
        RunContext(deps=MemAgentDeps(async_test_db, reads.current), model=TestModel(), usage=RunUsage()), "Alpha"
    )
    assert search.count == 1 and [row.term for row in search.terms] == ["Alpha"]
    draft.review_status = ReviewStatus.REJECTED
    await async_test_db.flush()
    assert (
        await read_conventions(
            async_test_db,
            reads.current.memory_group_id,
            workspace_id=reads.current.workspace_id,
            category=ConventionCategory.NAMING,
            review_statuses=[ReviewStatus.PENDING],
        )
        == []
    )


async def test_continuity_and_event_guards_use_shadow_visibility(async_test_db: AsyncSession, reads: ReadScenario):
    await write_continuity_summary(async_test_db, reads.predecessor, "Published handoff.")
    summary = (await async_test_db.scalars(select(Memory).where(Memory.plugin_name == "continuity"))).one()
    staged_summary = await _stage(async_test_db, ShadowMemory, reads.current, summary, memory_content="Draft handoff.")
    assert await read_previous_continuity_summary(async_test_db, reads.current) == "Draft handoff."
    assert await read_previous_continuity_summary(async_test_db, reads.other) == "Published handoff."
    staged_summary.deleted = True
    await async_test_db.flush()
    assert await read_previous_continuity_summary(async_test_db, reads.current) is None

    await access.create_term(async_test_db, reads.published.memory_group_id, "Alpha")
    event, _ = await access.create_memory(
        async_test_db,
        reads.predecessor,
        Creator.AGENT,
        MemoryType.EVENT,
        ["Alpha"],
        "An occurrence.",
        Scope.PERSIST,
        "gender.event.transformation",
    )
    staged_event = await _stage(async_test_db, ShadowMemory, reads.current, event, memory_end_num=2)
    chapter_num, history = await access.read_agent_event_history(
        async_test_db, reads.current, "Alpha", "gender.event.transformation"
    )
    assert chapter_num == 2 and [row.memory_end_num for row in history] == [2]
    assert not await access.can_supersede_agent_event(
        async_test_db, reads.current, event.memory_id, "Alpha", "gender.event.transformation"
    )
    assert await access.can_supersede_agent_event(
        async_test_db, reads.other, event.memory_id, "Alpha", "gender.event.transformation"
    )
    staged_event.deleted = True
    await async_test_db.flush()
    assert await access.read_agent_event_history(
        async_test_db, reads.current, "Alpha", "gender.event.transformation"
    ) == (2, [])
