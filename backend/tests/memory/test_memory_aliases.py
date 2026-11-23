"""Identity aliases expand only the shared character and relation readers."""

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary.aliases import (
    expire_alias_memory,
    new_alias_memory,
    supersede_alias_memory,
)
from src.memory.agent.toolsets.glossary.character_state import character_state_memories
from src.memory.agent.toolsets.glossary.relations import expire_relation_memory, relation_memories
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.glossary import access
from src.memory.types import Creator, MemoryType, ReviewStatus
from src.novels.models import ChapterContent
from test_support.test_data.scenarios import DatabaseScenario


@pytest.fixture
async def alias_context(async_test_db: AsyncSession, sample_scenario: DatabaseScenario) -> RunContext[MemAgentDeps]:
    group = MemoryGroup(
        memory_group_name="Alias retrieval",
        novel_id=sample_scenario.novels["novel_1"].novel_id,
        memory_language="en",
    )
    async_test_db.add(group)
    await async_test_db.flush()
    for name in ("Alpha", "Beta", "Gamma", "Delta", "Unrelated"):
        await access.create_term(async_test_db, group.memory_group_id, name)
    return RunContext(
        deps=MemAgentDeps(
            db=async_test_db,
            mem_access_context=MemAccessContext(
                memory_group_id=group.memory_group_id,
                chapter_id=sample_scenario.chapters["chapter_1"].chapter_id,
                chapter_content_id=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
            ),
        ),
        model=TestModel(),
        usage=RunUsage(),
    )


async def _memory(
    ctx: RunContext[MemAgentDeps], terms: list[str], content: str, memory_type: MemoryType, mark: str
) -> str:
    memory, _ = await access.create_memory(
        ctx.deps.db, ctx.deps.mem_access_context, Creator.AGENT, memory_type, terms, content, mark=mark
    )
    return ctx.deps.memory_handles.new(memory.memory_id)


async def test_alias_readers_expand_active_transitive_pairs_without_merging_forms(
    alias_context: RunContext[MemAgentDeps],
) -> None:
    ctx = alias_context
    alpha_beta = await _memory(
        ctx, ["Alpha", "Beta"], "Alpha is Beta's alternate spelling.", MemoryType.RELATION, "alias.spelling"
    )
    beta_gamma = await _memory(ctx, ["Beta", "Gamma"], "Beta is Gamma's persona.", MemoryType.RELATION, "alias.persona")
    gamma_delta = await _memory(
        ctx, ["Gamma", "Delta"], "Gamma is Delta's transformed form.", MemoryType.RELATION, "alias.transformation"
    )
    beta_fact = await _memory(ctx, ["Beta"], "Beta has black hair.", MemoryType.FACT, "appearance.hair")
    gamma_fact = await _memory(ctx, ["Gamma"], "Gamma has silver hair.", MemoryType.FACT, "appearance.hair")
    delta_fact = await _memory(ctx, ["Delta"], "Delta has gold hair.", MemoryType.FACT, "appearance.hair")
    friendship = await _memory(
        ctx, ["Delta", "Unrelated"], "Delta trusts Unrelated.", MemoryType.RELATION, "friendship"
    )
    await ctx.deps.db.flush()

    state = await character_state_memories(ctx, "Alpha", limit=1)
    assert state.count == 3
    assert state.rows[0].memory.memory_id in {beta_fact, gamma_fact, delta_fact}
    assert {term.term for row in state.rows + state.aliases for term in row.terms} >= {"Beta", "Gamma", "Delta"}
    assert state.aliases_truncated is False
    second = await character_state_memories(ctx, "Alpha", skip=1, limit=1)
    assert second.count == 3
    third = await character_state_memories(ctx, "Alpha", skip=2, limit=1)
    assert {row.memory.memory_id for row in state.rows + second.rows + third.rows} == {
        beta_fact,
        gamma_fact,
        delta_fact,
    }
    assert {term.term for row in state.rows + second.rows + third.rows for term in row.terms} == {
        "Beta",
        "Gamma",
        "Delta",
    }

    relations = await relation_memories(ctx, "Alpha", "friendship")
    assert [row.memory.memory_id for row in relations.rows] == [friendship]
    assert {row.memory.memory_id for row in relations.aliases} == {alpha_beta, beta_gamma, gamma_delta}
    aliases = await relation_memories(ctx, "Alpha", "alias")
    assert {row.memory.memory_id for row in aliases.rows} == {alpha_beta, beta_gamma, gamma_delta}
    assert {row.memory.memory_id for row in aliases.aliases} == {alpha_beta, beta_gamma, gamma_delta}
    assert {row.memory.mark for row in aliases.aliases} == {
        "alias.spelling",
        "alias.persona",
        "alias.transformation",
    }


async def test_expiring_alias_edge_splits_transitive_retrieval(
    alias_context: RunContext[MemAgentDeps], sample_scenario: DatabaseScenario
) -> None:
    ctx = alias_context
    await _memory(ctx, ["Alpha", "Beta"], "Alpha is Beta.", MemoryType.RELATION, "alias.transformation")
    beta_gamma = await _memory(ctx, ["Beta", "Gamma"], "Beta is Gamma.", MemoryType.RELATION, "alias.persona")
    await _memory(ctx, ["Gamma"], "Gamma has silver hair.", MemoryType.FACT, "appearance.hair")
    next_content = ChapterContent(
        chapter_id=sample_scenario.chapters["chapter_2"].chapter_id,
        chapter_content_version=1,
        chapter_content_text="Alpha returns.",
    )
    ctx.deps.db.add(next_content)
    await ctx.deps.db.flush()
    ctx.deps.mem_access_context = MemAccessContext(
        memory_group_id=ctx.deps.mem_access_context.memory_group_id,
        chapter_id=next_content.chapter_id,
        chapter_content_id=next_content.chapter_content_id,
    )
    await expire_alias_memory(ctx, beta_gamma)
    assert (await character_state_memories(ctx, "Alpha")).count == 0


async def test_legacy_pair_remains_expandable_but_multi_party_or_rejected_alias_does_not_expand(
    alias_context: RunContext[MemAgentDeps],
) -> None:
    ctx = alias_context
    legacy_pair = await _memory(ctx, ["Alpha", "Beta"], "Legacy pair alias.", MemoryType.RELATION, "alias")
    await _memory(ctx, ["Alpha", "Beta", "Gamma"], "Legacy broad alias.", MemoryType.RELATION, "alias")
    await _memory(ctx, ["Beta"], "Beta has black hair.", MemoryType.FACT, "appearance.hair")
    rejected = await _memory(ctx, ["Alpha", "Gamma"], "Rejected alias.", MemoryType.RELATION, "alias")
    await ctx.deps.db.execute(
        update(Memory)
        .where(Memory.memory_id == ctx.deps.memory_handles.get_uuid(rejected))
        .values(memory_review_status=ReviewStatus.REJECTED)
    )
    await ctx.deps.db.flush()
    page = await character_state_memories(ctx, "Alpha")
    assert [row.memory.memory_content for row in page.rows] == ["Beta has black hair."]
    assert [row.memory.memory_id for row in page.aliases] == [legacy_pair]


async def test_alias_expansion_reports_a_reached_term_cap(
    alias_context: RunContext[MemAgentDeps], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = alias_context
    await _memory(ctx, ["Alpha", "Beta"], "Alpha is Beta.", MemoryType.RELATION, "alias.spelling")
    await _memory(ctx, ["Beta", "Gamma"], "Beta is Gamma.", MemoryType.RELATION, "alias.persona")
    await _memory(ctx, ["Gamma"], "Gamma has silver hair.", MemoryType.FACT, "appearance.hair")
    monkeypatch.setattr(access, "MAX_ALIAS_TERMS", 2)
    page = await character_state_memories(ctx, "Alpha")
    assert page.aliases_truncated is True
    assert page.count == 0


async def test_alias_writer_persists_pair_and_rejects_generic_alias_lifecycle(
    alias_context: RunContext[MemAgentDeps], sample_scenario: DatabaseScenario
) -> None:
    ctx = alias_context
    with pytest.raises(ModelRetry):
        await new_alias_memory(ctx, "Not a pair.", ["Alpha", "Alpha"], "spelling")
    handle = await new_alias_memory(ctx, "Alpha is Beta.", ["Alpha", "Beta"], "transformation")
    memory_id = ctx.deps.memory_handles.get_uuid(handle)
    memory = await ctx.deps.db.get(Memory, memory_id)
    assert memory is not None and memory.mark == "alias.transformation" and memory.memory_end_num is None
    with pytest.raises(ModelRetry):
        await supersede_alias_memory(ctx, handle, "Wrong.", ["Alpha", "Beta", "Gamma"], "persona")
    next_content = ChapterContent(
        chapter_id=sample_scenario.chapters["chapter_2"].chapter_id,
        chapter_content_version=1,
        chapter_content_text="Alpha returns.",
    )
    ctx.deps.db.add(next_content)
    await ctx.deps.db.flush()
    ctx.deps.mem_access_context = MemAccessContext(
        memory_group_id=ctx.deps.mem_access_context.memory_group_id,
        chapter_id=next_content.chapter_id,
        chapter_content_id=next_content.chapter_content_id,
    )
    with pytest.raises(ModelRetry):
        await expire_relation_memory(ctx, handle)
