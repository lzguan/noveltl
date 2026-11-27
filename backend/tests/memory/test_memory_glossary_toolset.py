from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pydantic_ai import FunctionToolset, ModelRetry, RunContext, RunUsage
from pydantic_ai.capabilities import AbstractCapability, Toolset
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.test import TestModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.access import MemAccessContext
from src.memory.agent.agents.recording import (
    GLOSSARY_TOOLSET_NAMES,
    capability_factories_by_name,
    resolve_capabilities,
)
from src.memory.agent.config import JobParamsV1 as JobParams
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.conventions.tools import conventions_read_toolset
from src.memory.agent.toolsets.glossary import common as glossary_common
from src.memory.agent.toolsets.glossary.character_state import (
    character_state_memories,
    glossary_character_state_read_toolset,
)
from src.memory.agent.toolsets.glossary.definitions import (
    new_definition_memory,
)
from src.memory.agent.toolsets.glossary.facts import (
    fact_memories,
    glossary_facts_read_toolset,
    new_fact_memory,
)
from src.memory.agent.toolsets.glossary.gender import (
    glossary_gender_read_toolset,
    new_gender_memory,
)
from src.memory.agent.toolsets.glossary.gender_advanced_facts import (
    gender_state,
    glossary_gender_advanced_facts_read_toolset,
    glossary_gender_advanced_facts_write_toolset,
    new_gender_fact_memory,
)
from src.memory.agent.toolsets.glossary.gender_advanced_relations import (
    glossary_gender_advanced_relations_read_toolset,
    glossary_gender_advanced_relations_write_toolset,
)
from src.memory.agent.toolsets.glossary.instructions.gender_transformation import (
    glossary_gender_transformation_toolset,
)
from src.memory.agent.toolsets.glossary.relations import (
    new_relation_memory,
)
from src.memory.agent.toolsets.translations.tools import translations_read_toolset
from src.memory.agent.types import OccurrenceRetentionConfig, ParsedToolsets, ToolsetConfig
from src.memory.exceptions import GlossaryTermNotFoundException
from src.memory.models import MemoryGroup
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory, AgentGlossaryTerm
from src.memory.plugins.glossary.types import TermKind
from src.memory.schemas import AgentMemory
from src.memory.types import Creator, MemoryType, ReviewStatus
from src.schemas import Page
from test_support.test_data.scenarios import DatabaseScenario


def _run_context(db: AsyncSession) -> RunContext[MemAgentDeps]:
    deps = MemAgentDeps(
        db=db,
        mem_access_context=MemAccessContext(
            memory_group_id=uuid4(),
            chapter_id=uuid4(),
            chapter_content_id=uuid4(),
        ),
    )
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def _toolset(capability: AbstractCapability[MemAgentDeps]) -> FunctionToolset[MemAgentDeps]:
    assert isinstance(capability, Toolset)
    assert isinstance(capability.toolset, FunctionToolset)
    return capability.toolset


def test_guidance_toolsets_add_no_callable_tools_and_resolve_in_canonical_order() -> None:
    resolved = resolve_capabilities(
        ParsedToolsets(
            glossary_gender_advanced_facts_write={},
            glossary_gender_advanced_relations_write={},
            glossary_gender_transformation={},
            glossary_character_read={},
        )
    )

    assert [_toolset(capability) for capability in resolved] == [
        glossary_character_state_read_toolset,
        glossary_gender_advanced_facts_write_toolset,
        glossary_gender_advanced_relations_write_toolset,
        glossary_gender_transformation_toolset,
    ]
    assert glossary_gender_transformation_toolset.tools == {}


def test_continuity_only_selection_does_not_enable_glossary_context() -> None:
    assert "continuity_summary" not in GLOSSARY_TOOLSET_NAMES
    resolved = resolve_capabilities(ParsedToolsets(continuity_summary={}))
    assert len(resolved) == 1
    assert not isinstance(resolved[0], Toolset)


@pytest.mark.parametrize(
    "selection",
    [
        {"glossary_character_read": {}},
        {"glossary_character_read": {}, "glossary_relations_read": {}},
    ],
)
def test_character_reader_is_exposed_once_without_enabling_writers(selection: dict[str, dict]) -> None:
    resolved = resolve_capabilities(ParsedToolsets.model_validate(selection))
    names = [name for capability in resolved for name in _toolset(capability).tools]
    assert names.count("character_state_memories") == 1
    assert len(names) == len(set(names))
    assert not any(name.startswith(("new_", "supersede_", "expire_")) for name in names)


async def test_advanced_gender_event_write_config_is_applied_when_resolving_toolsets() -> None:
    resolved = resolve_capabilities(
        ParsedToolsets.model_validate(
            {
                "glossary_gender_advanced_events_read": {},
                "glossary_gender_advanced_events_write": {"keepFirst": 2, "keepRolling": 4},
            }
        )
    )

    write_toolset = _toolset(resolved[1])
    instructions = await write_toolset.get_instructions(_run_context(MagicMock(spec=AsyncSession)))
    assert instructions is not None
    assert any(
        "keep the first 2 occurrence(s) and a FIFO window of the newest 4 occurrence(s)" in instruction.content
        for instruction in instructions
    )


def test_job_params_reject_writes_and_guidance_without_required_toolsets() -> None:
    with pytest.raises(
        ValidationError,
        match="Toolset glossary_character_write requires: glossary_character_read",
    ):
        JobParams(
            model_name="deepseek:deepseek-v4-flash-low",
            toolsets={"glossary_character_write": {}},
        )

    with pytest.raises(
        ValidationError,
        match="Toolset glossary_gender_transformation requires: glossary_gender_advanced_facts_write",
    ):
        JobParams(
            model_name="deepseek:deepseek-v4-flash-low",
            toolsets={
                "glossary_character_read": {},
                "glossary_gender_transformation": {},
            },
        )

    with pytest.raises(
        ValidationError,
        match=("Toolset glossary_gender_transformation requires: glossary_gender_advanced_relations_write"),
    ):
        JobParams(
            model_name="deepseek:deepseek-v4-flash-low",
            toolsets={
                "glossary_character_read": {},
                "glossary_gender_advanced_facts_write": {},
                "glossary_gender_transformation": {},
            },
        )


async def test_create_memory_diagnoses_missing_terms_only_after_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=AsyncSession)
    create_memory = AsyncMock(side_effect=GlossaryTermNotFoundException("Some terms do not exist."))
    get_missing_term_names = AsyncMock(return_value=["金虚宫"])
    monkeypatch.setattr(glossary_common.access, "create_memory", create_memory)
    monkeypatch.setattr(glossary_common.access, "get_missing_term_names", get_missing_term_names)

    with pytest.raises(ModelRetry, match=r'Missing glossary terms: \["金虚宫"\]'):
        await glossary_common.create_memory(
            _run_context(db),
            "A memory.",
            ["金虚宫", "炽焰山"],
            MemoryType.DEFINITION,
            None,
            "new_definition_memory",
        )

    get_missing_term_names.assert_called_once()


async def test_create_memory_skips_missing_term_query_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=AsyncSession)
    memory_id = uuid4()
    create_memory = AsyncMock(return_value=(Mock(memory_id=memory_id), []))
    get_missing_term_names = AsyncMock()
    monkeypatch.setattr(glossary_common.access, "create_memory", create_memory)
    monkeypatch.setattr(glossary_common.access, "get_missing_term_names", get_missing_term_names)

    ctx = _run_context(db)
    handle = await glossary_common.create_memory(
        ctx,
        "A memory.",
        ["金虚宫"],
        MemoryType.DEFINITION,
        None,
        "new_definition_memory",
    )

    assert ctx.deps.memory_handles.get_uuid(handle) == memory_id
    get_missing_term_names.assert_not_called()


async def test_term_write_persists_categories_without_leaking_markers_into_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock(spec=AsyncSession)
    create_memory = AsyncMock(return_value=(Mock(memory_id=uuid4()), []))
    monkeypatch.setattr(glossary_common.access, "create_memory", create_memory)
    ctx = _run_context(db)

    await new_fact_memory(
        ctx,
        "[species] [species] Alpha is human.",
        ["Alpha"],
        "species",
    )
    await new_definition_memory(
        ctx,
        "A personal name.",
        ["Alpha"],
    )
    await new_relation_memory(
        ctx,
        "[friendship] [friendship] Alpha is friends with Beta.",
        ["Alpha", "Beta"],
        "friendship",
    )
    await new_gender_memory(ctx, "[gender] Alpha is a woman.", ["Alpha"])

    assert create_memory.call_args_list[0].args[5] == "Alpha is human."
    assert create_memory.call_args_list[0].args[7] == "species"
    assert create_memory.call_args_list[1].args[5] == "A personal name."
    assert create_memory.call_args_list[1].args[7] is None
    assert create_memory.call_args_list[2].args[5] == "Alpha is friends with Beta."
    assert create_memory.call_args_list[2].args[7] == "friendship"
    assert create_memory.call_args_list[3].args[5] == "Alpha is a woman."
    assert create_memory.call_args_list[3].args[7] == "gender"


def test_retrieval_tool_result_serializes_agent_models_with_snake_case() -> None:
    result = Page[AgentGlossaryMemory[str]](
        count=1,
        rows=[
            AgentGlossaryMemory[str](
                memory=AgentMemory[str](
                    memory_id="m1",
                    memory_type=MemoryType.FACT,
                    mark="species",
                    memory_content="Alpha is human.",
                    memory_start_num=1,
                    memory_review_status=ReviewStatus.PENDING,
                    memory_end_num=None,
                ),
                terms=[
                    AgentGlossaryTerm(
                        term="Alpha",
                        term_kind=TermKind.PERSON,
                        review_status=ReviewStatus.PENDING,
                    )
                ],
            )
        ],
    )

    serialized = ToolReturnPart(
        tool_name="fact_memories",
        content=result,
        tool_call_id="call-1",
    ).model_response_object()

    assert serialized == {
        "count": 1,
        "rows": [
            {
                "memory": {
                    "memory_id": "m1",
                    "memory_type": "fact",
                    "mark": "species",
                    "memory_content": "Alpha is human.",
                    "memory_start_num": 1,
                    "memory_review_status": "pending",
                    "memory_end_num": None,
                },
                "terms": [
                    {
                        "term": "Alpha",
                        "term_kind": "person",
                        "review_status": "pending",
                    }
                ],
            }
        ],
    }


async def test_fact_retrieval_combines_abilities_and_limitations_before_pagination(
    async_test_db: AsyncSession,
    sample_scenario: DatabaseScenario,
) -> None:
    group = MemoryGroup(
        memory_group_name="Fact retrieval",
        novel_id=sample_scenario.novels["novel_1"].novel_id,
        memory_language="en",
    )
    async_test_db.add(group)
    await async_test_db.flush()
    ctx = _run_context(async_test_db)
    ctx.deps.mem_access_context = MemAccessContext(
        memory_group_id=group.memory_group_id,
        chapter_id=sample_scenario.chapters["chapter_1"].chapter_id,
        chapter_content_id=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
    )
    await glossary_common.access.create_term(async_test_db, group.memory_group_id, "Alpha")
    for mark, content in (
        ("ability", "Alpha can channel magic through marked gates."),
        ("limitation", "Alpha is vulnerable to silver magic."),
        ("limitation", "Alpha cannot swim."),
        ("species", "Alpha is a magical human."),
        ("trait", "Alpha has a legacy magic trait."),
    ):
        await glossary_common.access.create_memory(
            async_test_db,
            ctx.deps.mem_access_context,
            Creator.AGENT,
            MemoryType.FACT,
            ["Alpha"],
            content,
            mark=mark,
        )
    await async_test_db.flush()

    ability_page = await fact_memories(ctx, "Alpha", "ability", term_search="MAGIC")
    limitation_page = await fact_memories(ctx, "Alpha", "limitation", term_search="MAGIC")
    assert ability_page == limitation_page
    assert ability_page.count == 2
    assert {row.memory.mark for row in ability_page.rows} == {"ability", "limitation"}
    first = await fact_memories(ctx, "Alpha", "ability", limit=1, term_search="MAGIC")
    second = await fact_memories(ctx, "Alpha", "limitation", skip=1, limit=1, term_search="MAGIC")
    assert first.count == second.count == 2
    assert first.rows + second.rows == ability_page.rows
    species_page = await fact_memories(ctx, "Alpha", "species")
    assert species_page.count == 1
    assert species_page.rows[0].memory.mark == "species"

    # Shared reads find specialized state even though generic writers cannot own it.
    for mark in ("gender", "gender.body", "gender.identity", "gender.presentation", "gender.change_rule"):
        await glossary_common.access.create_memory(
            async_test_db,
            ctx.deps.mem_access_context,
            Creator.AGENT,
            MemoryType.FACT,
            ["Alpha"],
            f"Alpha has recorded state for {mark}.",
            mark=mark,
        )
    await glossary_common.access.create_memory(
        async_test_db,
        ctx.deps.mem_access_context,
        Creator.AGENT,
        MemoryType.EVENT,
        ["Alpha"],
        "Alpha changed during an event.",
        mark="gender.event.transformation",
    )
    await glossary_common.access.create_memory(
        async_test_db,
        ctx.deps.mem_access_context,
        Creator.AGENT,
        MemoryType.RELATION,
        ["Alpha"],
        "An observer perceives Alpha differently.",
        mark="gender.perception",
    )
    shared = await character_state_memories(ctx, "Alpha")
    assert shared.count == 9
    assert {row.memory.mark for row in shared.rows} == {
        "ability",
        "limitation",
        "species",
        "gender",
        "gender.body",
        "gender.identity",
        "gender.presentation",
        "gender.change_rule",
    }
    assert all(row.memory.memory_type == MemoryType.FACT for row in shared.rows)
    shared_first = await character_state_memories(ctx, "Alpha", limit=4)
    shared_rest = await character_state_memories(ctx, "Alpha", skip=4)
    assert shared_first.count == shared_rest.count == 9
    assert shared_first.rows + shared_rest.rows == shared.rows
    assert (await character_state_memories(ctx, "Alpha", term_search="recorded state")).count == 5


async def test_advanced_gender_state_groups_namespaced_aspects(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=AsyncSession)
    body = AgentGlossaryMemory(
        memory=AgentMemory(
            memory_id=uuid4(),
            memory_type=MemoryType.FACT,
            mark="gender.body",
            memory_content="Alpha's current body is female.",
            memory_start_num=1,
            memory_review_status=ReviewStatus.PENDING,
            memory_end_num=None,
        ),
        terms=[],
    )
    identity = AgentGlossaryMemory(
        memory=AgentMemory(
            memory_id=uuid4(),
            memory_type=MemoryType.FACT,
            mark="gender.identity",
            memory_content="Alpha self-identifies as male.",
            memory_start_num=1,
            memory_review_status=ReviewStatus.PENDING,
            memory_end_num=None,
        ),
        terms=[],
    )
    presentation = AgentGlossaryMemory(
        memory=AgentMemory(
            memory_id=uuid4(),
            memory_type=MemoryType.FACT,
            mark="gender.presentation",
            memory_content="Alpha ordinarily presents as a woman.",
            memory_start_num=1,
            memory_review_status=ReviewStatus.PENDING,
            memory_end_num=None,
        ),
        terms=[],
    )
    change_rule = AgentGlossaryMemory(
        memory=AgentMemory(
            memory_id=uuid4(),
            memory_type=MemoryType.FACT,
            mark="gender.change_rule",
            memory_content="Alpha changes body under moonlight.",
            memory_start_num=1,
            memory_review_status=ReviewStatus.PENDING,
            memory_end_num=None,
        ),
        terms=[],
    )
    monkeypatch.setattr(
        glossary_common.access,
        "inspect_terms",
        AsyncMock(return_value=Page(count=4, rows=[body, identity, presentation, change_rule])),
    )

    state = await gender_state(_run_context(db), "Alpha")

    assert [row.memory.memory_content for row in state.body] == ["Alpha's current body is female."]
    assert [row.memory.memory_content for row in state.identity] == ["Alpha self-identifies as male."]
    assert [row.memory.memory_content for row in state.presentation] == ["Alpha ordinarily presents as a woman."]
    assert [row.memory.memory_content for row in state.change_rule] == ["Alpha changes body under moonlight."]


async def test_advanced_gender_create_rejects_second_active_aspect(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=AsyncSession)
    monkeypatch.setattr(glossary_common.access, "inspect_terms", AsyncMock(return_value=Page(count=1, rows=[])))

    with pytest.raises(ModelRetry, match="already has an active body memory"):
        await new_gender_fact_memory(
            _run_context(db),
            "Alpha",
            "body",
            "Alpha's current body is female.",
        )


async def test_advanced_gender_create_allows_multiple_change_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=AsyncSession)
    inspect_terms = AsyncMock(return_value=Page(count=1, rows=[]))
    create_memory = AsyncMock(return_value="m1")
    monkeypatch.setattr(glossary_common.access, "inspect_terms", inspect_terms)
    monkeypatch.setattr(glossary_common, "create_memory", create_memory)

    result = await new_gender_fact_memory(
        _run_context(db),
        "Alpha",
        "change_rule",
        "Alpha changes body under moonlight.",
    )

    assert result == "m1"
    inspect_terms.assert_not_called()
    assert create_memory.call_args.args[6] == "gender.change_rule"


def test_callable_memory_toolsets_require_sequential_execution() -> None:
    toolsets: dict[str, FunctionToolset[MemAgentDeps]] = {
        "conventions_read": conventions_read_toolset,
        "translations_read": translations_read_toolset,
        "glossary_facts_read": glossary_facts_read_toolset,
        "glossary_gender_read": glossary_gender_read_toolset,
        "glossary_gender_advanced_facts_read": glossary_gender_advanced_facts_read_toolset,
        "glossary_gender_advanced_relations_read": glossary_gender_advanced_relations_read_toolset,
    }
    for name, factory in capability_factories_by_name.items():
        config = OccurrenceRetentionConfig() if name == "glossary_gender_advanced_events_write" else ToolsetConfig()
        capability = factory(config)
        if isinstance(capability, Toolset) and isinstance(capability.toolset, FunctionToolset):
            toolsets[name] = capability.toolset

    callable_toolsets = {name: toolset for name, toolset in toolsets.items() if toolset.tools}
    assert callable_toolsets
    for name, toolset in callable_toolsets.items():
        assert toolset.sequential is True, f"{name} must be sequential=True because tools share one AsyncSession"
        for tool_name, tool in toolset.tools.items():
            assert tool.sequential is True, f"{name}.{tool_name} must be sequential=True"


def test_job_params_reject_unknown_toolsets_and_settings() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        JobParams(
            model_name="deepseek:deepseek-v4-flash-low",
            toolsets={"unknown_toolset": {}},
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        JobParams(
            model_name="deepseek:deepseek-v4-flash-low",
            toolsets={"glossary_terms": {"unknown_setting": True}},
        )

    with pytest.raises(ValidationError, match="Input should be less than or equal to 20"):
        JobParams(
            model_name="deepseek:deepseek-v4-flash-low",
            toolsets={
                "glossary_gender_advanced_events_read": {},
                "glossary_gender_advanced_events_write": {"keepFirst": 21},
            },
        )
