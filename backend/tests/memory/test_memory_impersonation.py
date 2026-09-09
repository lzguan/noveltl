"""Directional impersonation context stays separate from identity aliases."""

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary.aliases import (
    expire_alias_memory,
    supersede_alias_memory,
)
from src.memory.agent.toolsets.glossary.character_state import character_state_memories
from src.memory.agent.toolsets.glossary.impersonation import (
    expire_impersonation_memory,
    new_impersonation_memory,
    supersede_impersonation_memory,
)
from src.memory.agent.toolsets.glossary.relations import (
    expire_relation_memory,
    supersede_relation_memory,
)
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.memory.types import Creator, MemoryType
from src.novels.models import ChapterContent
from test_support.test_data.scenarios import DatabaseScenario


@pytest.fixture
def impersonation_context(test_db: Session, sample_scenario: DatabaseScenario) -> RunContext[MemAgentDeps]:
    group = MemoryGroup(
        memory_group_name="Impersonation retrieval",
        novel_id=sample_scenario.novels["novel_1"].novel_id,
        memory_language="en",
    )
    test_db.add(group)
    test_db.flush()
    for name in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon"):
        access.create_term(test_db, group.memory_group_id, name)
    return RunContext(
        deps=MemAgentDeps(
            db=test_db,
            mem_access_context=MemAccessContext(
                memory_group_id=group.memory_group_id,
                chapter_id=sample_scenario.chapters["chapter_1"].chapter_id,
                chapter_content_id=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
            ),
        ),
        model=TestModel(),
        usage=RunUsage(),
    )


def _memory(
    ctx: RunContext[MemAgentDeps], terms: list[str], content: str, memory_type: MemoryType, mark: str
) -> str:
    memory, _ = access.create_memory(
        ctx.deps.db, ctx.deps.mem_access_context, Creator.AGENT, memory_type, terms, content, mark=mark
    )
    return ctx.deps.uuid_cache.new(memory.memory_id)


def _advance_to_chapter_two(
    ctx: RunContext[MemAgentDeps], sample_scenario: DatabaseScenario
) -> MemAccessContext:
    content = ChapterContent(
        chapter_id=sample_scenario.chapters["chapter_2"].chapter_id,
        chapter_content_version=1,
        chapter_content_text="The disguise continues.",
    )
    ctx.deps.db.add(content)
    ctx.deps.db.flush()
    context = MemAccessContext(
        memory_group_id=ctx.deps.mem_access_context.memory_group_id,
        chapter_id=content.chapter_id,
        chapter_content_id=content.chapter_content_id,
    )
    ctx.deps.mem_access_context = context
    return context


def test_character_state_keeps_impersonations_separate_and_pages_alias_context(
    impersonation_context: RunContext[MemAgentDeps],
) -> None:
    ctx = impersonation_context
    alias = _memory(ctx, ["Alpha", "Beta"], "Alpha is Beta's persona.", MemoryType.RELATION, "alias.persona")
    beta_fact = _memory(ctx, ["Beta"], "Beta has black hair.", MemoryType.FACT, "appearance.hair")
    gamma_fact = _memory(ctx, ["Gamma"], "Gamma has silver hair.", MemoryType.FACT, "appearance.hair")
    first = new_impersonation_memory(ctx, "Beta", "Gamma", "He uses Gamma's name.")
    second = new_impersonation_memory(ctx, "Beta", "Delta", "The ruse is ongoing.")
    third = new_impersonation_memory(ctx, "Beta", "Epsilon", "This cover remains active.")
    ctx.deps.db.flush()

    state = character_state_memories(ctx, "Alpha", limit=1, impersonation_skip=0)
    assert state.count == 1
    assert [row.memory.memory_id for row in state.rows] == [beta_fact]
    assert state.aliases_truncated is False
    assert [row.memory.memory_id for row in state.aliases] == [alias]
    assert state.impersonations.count == 3
    assert len(state.impersonations.rows) == 1

    next_page = character_state_memories(ctx, "Alpha", limit=1, impersonation_skip=1)
    final_page = character_state_memories(ctx, "Alpha", limit=1, impersonation_skip=2)
    assert {row.memory.memory_id for row in state.impersonations.rows + next_page.impersonations.rows + final_page.impersonations.rows} == {
        first,
        second,
        third,
    }

    gamma = character_state_memories(ctx, "Gamma")
    assert [row.memory.memory_id for row in gamma.rows] == [gamma_fact]
    assert [row.memory.memory_id for row in gamma.impersonations.rows] == [first]
    first_row = gamma.impersonations.rows[0]
    assert {term.term for term in first_row.terms} == {"Beta", "Gamma"}
    assert first_row.memory.memory_content == "Beta is impersonating Gamma. He uses Gamma's name."


def test_impersonation_supersession_is_directional_and_isolated_from_generic_lifecycles(
    impersonation_context: RunContext[MemAgentDeps], sample_scenario: DatabaseScenario
) -> None:
    ctx = impersonation_context
    with pytest.raises(ModelRetry):
        new_impersonation_memory(ctx, "Alpha", "Alpha", "Impossible self impersonation.")

    original_handle = new_impersonation_memory(ctx, "Alpha", "Beta", "The initial disguise.")
    original_id = ctx.deps.uuid_cache.get_uuid(original_handle)
    original = ctx.deps.db.get(Memory, original_id)
    assert original is not None
    assert original.mark == "impersonation"
    assert original.memory_content == "Alpha is impersonating Beta. The initial disguise."
    assert {
        term for term in ctx.deps.db.scalars(
            select(GlossaryTerm.term)
            .join(GlossaryAssociation, GlossaryAssociation.term_id == GlossaryTerm.term_id)
            .where(GlossaryAssociation.memory_id == original_id)
        )
    } == {"Alpha", "Beta"}

    _advance_to_chapter_two(ctx, sample_scenario)
    with pytest.raises(ModelRetry):
        supersede_alias_memory(ctx, original_handle, "Wrong writer.", ["Alpha", "Beta"], "persona")
    with pytest.raises(ModelRetry):
        expire_alias_memory(ctx, original_handle)
    with pytest.raises(ModelRetry):
        supersede_relation_memory(ctx, original_handle, "Wrong writer.", "friendship")
    with pytest.raises(ModelRetry):
        expire_relation_memory(ctx, original_handle)

    successor_handle = supersede_impersonation_memory(
        ctx, original_handle, "Beta", "Alpha", "The direction has reversed."
    )
    successor_id = ctx.deps.uuid_cache.get_uuid(successor_handle)
    successor = ctx.deps.db.get(Memory, successor_id)
    ctx.deps.db.refresh(original)
    assert successor is not None
    assert successor.mark == "impersonation"
    assert successor.supersedes_memory_id == original_id
    assert successor.memory_content == "Beta is impersonating Alpha. The direction has reversed."
    assert original.memory_end_num == 2
    assert [row.memory.memory_id for row in character_state_memories(ctx, "Alpha").impersonations.rows] == [successor_handle]


def test_expiring_impersonation_preserves_earlier_history(
    impersonation_context: RunContext[MemAgentDeps], sample_scenario: DatabaseScenario
) -> None:
    ctx = impersonation_context
    handle = new_impersonation_memory(ctx, "Alpha", "Beta", "The disguise is established.")
    memory_id = ctx.deps.uuid_cache.get_uuid(handle)
    chapter_one_context = ctx.deps.mem_access_context

    _advance_to_chapter_two(ctx, sample_scenario)
    assert expire_impersonation_memory(ctx, handle) == f"Memory {handle} expired successfully."
    memory = ctx.deps.db.get(Memory, memory_id)
    assert memory is not None and memory.memory_end_num == 2
    assert character_state_memories(ctx, "Alpha").impersonations.count == 0

    ctx.deps.mem_access_context = chapter_one_context
    earlier = character_state_memories(ctx, "Alpha")
    assert [row.memory.memory_id for row in earlier.impersonations.rows] == [handle]
