"""Shared reads must not let specialized character writers mutate other domains."""

import pytest
from pydantic_ai import FunctionToolset, ModelRetry, RunContext, RunUsage
from pydantic_ai.capabilities import AbstractCapability, Toolset
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.agent import resolve_capabilities
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary.appearance import (
    expire_appearance_memory,
    new_appearance_memory,
    supersede_appearance_memory,
)
from src.memory.agent.toolsets.glossary.character_state import character_state_memories
from src.memory.agent.toolsets.glossary.cultivation import (
    expire_cultivation_memory,
    new_cultivation_memory,
    supersede_cultivation_memory,
)
from src.memory.agent.toolsets.glossary.facts import expire_fact_memory, new_fact_memory
from src.memory.agent.types import ParsedToolsets
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.glossary.access import create_term
from src.novels.models import ChapterContent
from test_support.test_data.scenarios import DatabaseScenario


def _toolset(capability: AbstractCapability[MemAgentDeps]) -> FunctionToolset[MemAgentDeps]:
    assert isinstance(capability, Toolset)
    assert isinstance(capability.toolset, FunctionToolset)
    return capability.toolset


def test_character_writers_share_reads_but_preserve_mutation_ownership(
    test_db: Session,
    sample_scenario: DatabaseScenario,
) -> None:
    group = MemoryGroup(
        memory_group_name="Character writer ownership",
        novel_id=sample_scenario.novels["novel_1"].novel_id,
        memory_language="en",
    )
    test_db.add(group)
    test_db.flush()
    create_term(test_db, group.memory_group_id, "Alpha")
    deps = MemAgentDeps(
        db=test_db,
        mem_access_context=MemAccessContext(
            memory_group_id=group.memory_group_id,
            chapter_id=sample_scenario.chapters["chapter_1"].chapter_id,
            chapter_content_id=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
        ),
    )
    ctx = RunContext(deps=deps, model=TestModel(), usage=RunUsage())
    hair = new_appearance_memory(ctx, "Alpha", "hair", "Alpha has black hair.")
    attire = new_appearance_memory(ctx, "Alpha", "attire", "Alpha wears a recurring red uniform.")
    cultivation = new_cultivation_memory(ctx, "Alpha", "Alpha's spiritual cultivation is stage one.")
    ability = new_fact_memory(ctx, "Alpha can teleport.", ["Alpha"], "ability")
    state = character_state_memories(ctx, "Alpha")
    assert state.count == 4
    assert {row.memory.mark for row in state.rows} == {
        "appearance.hair",
        "appearance.attire",
        "cultivation_level",
        "ability",
    }

    next_content = ChapterContent(
        chapter_id=sample_scenario.chapters["chapter_2"].chapter_id,
        chapter_content_version=1,
        chapter_content_text="Alpha changes.",
    )
    test_db.add(next_content)
    test_db.flush()
    deps.mem_access_context = MemAccessContext(
        memory_group_id=group.memory_group_id,
        chapter_id=next_content.chapter_id,
        chapter_content_id=next_content.chapter_content_id,
    )
    with pytest.raises(ModelRetry):
        expire_fact_memory(ctx, hair)
    with pytest.raises(ModelRetry):
        expire_appearance_memory(ctx, cultivation)
    with pytest.raises(ModelRetry):
        expire_cultivation_memory(ctx, attire)
    with pytest.raises(ModelRetry):
        supersede_appearance_memory(ctx, ability, "Alpha", "hair", "Wrong domain.")
    with pytest.raises(ModelRetry):
        supersede_cultivation_memory(ctx, attire, "Alpha", "Wrong domain.")
    replacement = supersede_appearance_memory(ctx, hair, "Alpha", "hair", "Alpha's hair is now white.")
    new_level = supersede_cultivation_memory(ctx, cultivation, "Alpha", "Alpha's spiritual cultivation is stage two.")
    expire_appearance_memory(ctx, attire)
    remaining = character_state_memories(ctx, "Alpha")
    assert {row.memory.memory_id for row in remaining.rows} == {replacement, new_level, ability}
    ended = test_db.get(Memory, deps.uuid_cache.get_uuid(hair))
    assert ended is not None
    assert ended.memory_end_num == 2


@pytest.mark.parametrize(
    "writer,expected",
    [
        ("glossary_character_write", "new_fact_memory"),
        ("glossary_appearance_write", "new_appearance_memory"),
        ("glossary_cultivation_write", "new_cultivation_memory"),
        ("glossary_gender_advanced_facts_write", "new_gender_fact_memory"),
        ("glossary_gender_advanced_relations_write", "new_gender_perception_memory"),
    ],
)
def test_character_writers_are_independently_selectable(writer: str, expected: str) -> None:
    capabilities = resolve_capabilities(ParsedToolsets.model_validate({"glossary_character_read": {}, writer: {}}))
    names = [name for capability in capabilities for name in _toolset(capability).tools]
    assert names.count("character_state_memories") == 1
    assert "gender_perception_memories" in names
    assert [name for name in names if name.startswith("new_")] == [expected]
