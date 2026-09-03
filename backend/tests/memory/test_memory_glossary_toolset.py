from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.agent import resolve_toolsets
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.prompt import MEMORY_AGENT_PROMPT
from src.memory.agent.tasks.jobs import JobParams
from src.memory.agent.toolsets.glossary import common as glossary_common
from src.memory.agent.toolsets.glossary.context import GLOSSARY_SHARED_INSTRUCTIONS
from src.memory.agent.toolsets.glossary.definitions import (
    definition_memories,
    glossary_definitions_read_toolset,
    glossary_definitions_write_toolset,
    new_definition_memory,
)
from src.memory.agent.toolsets.glossary.events import glossary_events_read_toolset
from src.memory.agent.toolsets.glossary.facts import (
    fact_memories,
    glossary_facts_read_toolset,
    glossary_facts_write_toolset,
    new_fact_memory,
)
from src.memory.agent.toolsets.glossary.gender import (
    gender_memories,
    glossary_gender_write_toolset,
    new_gender_memory,
)
from src.memory.agent.toolsets.glossary.gender_advanced_events import (
    glossary_gender_advanced_events_read_toolset,
    glossary_gender_advanced_events_write_toolset,
)
from src.memory.agent.toolsets.glossary.gender_advanced_facts import (
    gender_state,
    glossary_gender_advanced_facts_read_toolset,
    glossary_gender_advanced_facts_write_toolset,
    new_gender_fact_memory,
)
from src.memory.agent.toolsets.glossary.gender_advanced_relations import (
    gender_perception_memories,
    glossary_gender_advanced_relations_read_toolset,
    glossary_gender_advanced_relations_write_toolset,
    new_gender_perception_memory,
)
from src.memory.agent.toolsets.glossary.guidance.gender_transformation import (
    glossary_gender_transformation_toolset,
)
from src.memory.agent.toolsets.glossary.relations import (
    glossary_relations_read_toolset,
    glossary_relations_write_toolset,
    new_relation_memory,
    relation_memories,
)
from src.memory.agent.toolsets.glossary.terms import glossary_term_toolset
from src.memory.agent.types import ParsedToolsets
from src.memory.exceptions import GlossaryTermNotFoundException
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory, AgentGlossaryTerm
from src.memory.plugins.glossary.types import TermKind
from src.memory.schemas import AgentMemory
from src.memory.types import MemoryType, ReviewStatus
from src.schemas import Page


def _run_context(db: Session) -> RunContext[MemAgentDeps]:
    deps = MemAgentDeps(
        db=db,
        mem_access_context=MemAccessContext(
            memory_group_id=uuid4(),
            chapter_id=uuid4(),
            chapter_content_id=uuid4(),
        ),
    )
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def test_memory_prompts_preserve_novel_terms_in_the_source_language() -> None:
    for instructions in (MEMORY_AGENT_PROMPT, GLOSSARY_SHARED_INSTRUCTIONS):
        normalized_instructions = " ".join(instructions.split()).lower()
        assert (
            "keep every novel-specific term exactly as it appears in the original source language"
            in normalized_instructions
        )
        assert "never translate, romanize, or replace" in normalized_instructions

    assert "Correct: `赤岚司 guards the northern archive.`" in MEMORY_AGENT_PROMPT
    assert "Wrong: `Crimson Mist Bureau guards the northern archive.`" in MEMORY_AGENT_PROMPT
    assert "Wrong: `赤岚司守卫着北方档案馆。`" in MEMORY_AGENT_PROMPT


def test_guidance_toolsets_add_no_callable_tools_and_resolve_in_canonical_order() -> None:
    resolved = resolve_toolsets(
        ParsedToolsets(
            glossary_gender_advanced_facts_write={},
            glossary_gender_advanced_relations_write={},
            glossary_gender_transformation={},
            glossary_gender_advanced_facts_read={},
            glossary_gender_advanced_relations_read={},
        )
    )

    assert resolved == [
        glossary_gender_advanced_facts_read_toolset,
        glossary_gender_advanced_facts_write_toolset,
        glossary_gender_advanced_relations_read_toolset,
        glossary_gender_advanced_relations_write_toolset,
        glossary_gender_transformation_toolset,
    ]
    assert glossary_gender_transformation_toolset.tools == {}


def test_job_params_reject_writes_and_guidance_without_required_toolsets() -> None:
    with pytest.raises(
        ValidationError,
        match="Toolset glossary_gender_write requires: glossary_gender_read",
    ):
        JobParams(
            model_name="deepseek:deepseek-v4-flash-low",
            toolsets={"glossary_gender_write": {}},
        )

    with pytest.raises(
        ValidationError,
        match="Toolset glossary_gender_transformation requires: glossary_gender_advanced_facts_write",
    ):
        JobParams(
            model_name="deepseek:deepseek-v4-flash-low",
            toolsets={
                "glossary_gender_advanced_facts_read": {},
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
                "glossary_gender_advanced_facts_read": {},
                "glossary_gender_advanced_facts_write": {},
                "glossary_gender_advanced_relations_read": {},
                "glossary_gender_transformation": {},
            },
        )


def test_create_memory_diagnoses_missing_terms_only_after_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=Session)
    create_memory = Mock(side_effect=GlossaryTermNotFoundException("Some terms do not exist."))
    get_missing_term_names = Mock(return_value=["金虚宫"])
    monkeypatch.setattr(glossary_common.access, "create_memory", create_memory)
    monkeypatch.setattr(glossary_common.access, "get_missing_term_names", get_missing_term_names)

    with pytest.raises(ModelRetry, match=r'Missing glossary terms: \["金虚宫"\]'):
        glossary_common.create_memory(
            _run_context(db),
            "A memory.",
            ["金虚宫", "炽焰山"],
            MemoryType.DEFINITION,
            None,
            "new_definition_memory",
        )

    get_missing_term_names.assert_called_once()


def test_create_memory_skips_missing_term_query_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=Session)
    memory_id = uuid4()
    create_memory = Mock(return_value=(Mock(memory_id=memory_id), []))
    get_missing_term_names = Mock()
    monkeypatch.setattr(glossary_common.access, "create_memory", create_memory)
    monkeypatch.setattr(glossary_common.access, "get_missing_term_names", get_missing_term_names)

    ctx = _run_context(db)
    handle = glossary_common.create_memory(
        ctx,
        "A memory.",
        ["金虚宫"],
        MemoryType.DEFINITION,
        None,
        "new_definition_memory",
    )

    assert ctx.deps.uuid_cache.get_uuid(handle) == memory_id
    get_missing_term_names.assert_not_called()


def test_glossary_tool_schemas_enforce_input_constraints() -> None:
    event_schema = glossary_events_read_toolset.tools["term_event_memories"].function_schema.json_schema
    assert event_schema["properties"]["skip"] == {"default": 0, "minimum": 0, "type": "integer"}
    assert event_schema["properties"]["limit"] == {
        "default": 10,
        "maximum": 20,
        "minimum": 1,
        "type": "integer",
    }
    assert event_schema["properties"]["active_only"] == {"default": True, "type": "boolean"}

    for toolset, tool_name, required in (
        (glossary_definitions_read_toolset, "definition_memories", ["term_name"]),
        (glossary_relations_read_toolset, "relation_memories", ["term_name", "category"]),
        (glossary_facts_read_toolset, "fact_memories", ["term_name", "category"]),
    ):
        term_schema = toolset.tools[tool_name].function_schema.json_schema
        assert term_schema["required"] == required
        assert term_schema["properties"]["term_name"] == {"minLength": 1, "type": "string"}
        assert "memory_kind" not in term_schema["properties"]
        assert "memory_type" not in term_schema["properties"]
        assert "mark" not in term_schema["properties"]
        assert term_schema["properties"]["skip"] == {"default": 0, "minimum": 0, "type": "integer"}
        assert term_schema["properties"]["limit"] == {
            "default": 5,
            "maximum": 20,
            "minimum": 1,
            "type": "integer",
        }
        assert term_schema["properties"]["term_search"]["anyOf"][0] == {
            "minLength": 1,
            "type": "string",
        }

    gender_event_read_schema = glossary_gender_advanced_events_read_toolset.tools[
        "gender_event_memories"
    ].function_schema.json_schema
    assert gender_event_read_schema["required"] == ["term_name", "event_kind"]
    assert gender_event_read_schema["properties"]["term_name"] == {"minLength": 1, "type": "string"}
    assert gender_event_read_schema["properties"]["skip"] == {
        "default": 0,
        "minimum": 0,
        "type": "integer",
    }

    add_term_schema = glossary_term_toolset.tools["add_term"].function_schema.json_schema
    assert add_term_schema["required"] == ["term_name", "term_kind"]
    assert add_term_schema["$defs"]["TermKind"]["enum"] == [
        "person",
        "place",
        "organization",
        "technique",
        "item",
        "concept",
        "title",
        "species",
        "other",
    ]
    for toolset, tool_name, required in (
        (glossary_definitions_write_toolset, "new_definition_memory", ["content", "term_names"]),
        (glossary_relations_write_toolset, "new_relation_memory", ["content", "term_names", "category"]),
        (glossary_facts_write_toolset, "new_fact_memory", ["content", "term_names", "category"]),
        (glossary_definitions_write_toolset, "supersede_definition_memory", ["memory_id", "content"]),
        (
            glossary_relations_write_toolset,
            "supersede_relation_memory",
            ["memory_id", "content", "category"],
        ),
        (
            glossary_facts_write_toolset,
            "supersede_fact_memory",
            ["memory_id", "content", "term_name", "category"],
        ),
    ):
        write_schema = toolset.tools[tool_name].function_schema.json_schema
        assert write_schema["required"] == required
        assert "memory_kind" not in write_schema["properties"]
        assert "memory_type" not in write_schema["properties"]

    for toolset, tool_name in (
        (glossary_definitions_write_toolset, "new_definition_memory"),
        (glossary_facts_write_toolset, "new_fact_memory"),
    ):
        term_names_schema = toolset.tools[tool_name].function_schema.json_schema["properties"]["term_names"]
        assert term_names_schema["minItems"] == 1
        assert term_names_schema["maxItems"] == 1

    relation_term_names_schema = glossary_relations_write_toolset.tools[
        "new_relation_memory"
    ].function_schema.json_schema["properties"]["term_names"]
    assert relation_term_names_schema["minItems"] == 2

    fact_schema = glossary_facts_write_toolset.tools["new_fact_memory"].function_schema.json_schema
    assert fact_schema["properties"]["category"] == {"$ref": "#/$defs/FactCategory"}
    assert fact_schema["$defs"]["FactCategory"]["enum"] == [
        "age_stage",
        "species",
        "appearance",
        "cultivation_level",
        "trait",
        "ability",
        "limitation",
    ]
    supersede_fact_schema = glossary_facts_write_toolset.tools["supersede_fact_memory"].function_schema.json_schema
    assert supersede_fact_schema["properties"]["term_name"] == {
        "minLength": 1,
        "type": "string",
    }
    gender_schema = glossary_gender_write_toolset.tools["new_gender_memory"].function_schema.json_schema
    assert gender_schema["required"] == ["content", "term_names"]
    assert "category" not in gender_schema["properties"]
    assert gender_schema["properties"]["term_names"]["maxItems"] == 1
    advanced_gender_schema = glossary_gender_advanced_facts_write_toolset.tools[
        "new_gender_fact_memory"
    ].function_schema.json_schema
    assert advanced_gender_schema["required"] == ["term_name", "aspect", "content"]
    assert advanced_gender_schema["properties"]["aspect"] == {"$ref": "#/$defs/GenderFactAspect"}
    assert advanced_gender_schema["$defs"]["GenderFactAspect"]["enum"] == [
        "body",
        "identity",
        "presentation",
        "change_rule",
    ]
    gender_perception_schema = glossary_gender_advanced_relations_write_toolset.tools[
        "new_gender_perception_memory"
    ].function_schema.json_schema
    assert gender_perception_schema["required"] == [
        "observer_term_name",
        "subject_term_name",
        "content",
    ]
    assert "mark" not in gender_perception_schema["properties"]
    assert "category" not in gender_perception_schema["properties"]
    gender_event_schema = glossary_gender_advanced_events_write_toolset.tools[
        "new_gender_event_memory"
    ].function_schema.json_schema
    assert gender_event_schema["$defs"]["GenderEventKind"]["enum"] == [
        "transformation",
        "body_swap",
        "possession",
        "reveal",
    ]
    relation_schema = glossary_relations_write_toolset.tools["new_relation_memory"].function_schema.json_schema
    assert relation_schema["properties"]["category"] == {"$ref": "#/$defs/RelationCategory"}
    assert relation_schema["$defs"]["RelationCategory"]["enum"] == [
        "alias",
        "kinship",
        "friendship",
        "romance",
        "mentorship",
        "rank",
        "membership",
        "service",
        "ownership",
        "alliance",
        "rivalry",
        "organizational_hierarchy",
        "commercial_partnership",
    ]


def test_term_write_persists_categories_without_leaking_markers_into_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock(spec=Session)
    create_memory = Mock(return_value=(Mock(memory_id=uuid4()), []))
    monkeypatch.setattr(glossary_common.access, "create_memory", create_memory)
    ctx = _run_context(db)

    new_fact_memory(
        ctx,
        "[species] [species] Alpha is human.",
        ["Alpha"],
        "species",
    )
    new_definition_memory(
        ctx,
        "A personal name.",
        ["Alpha"],
    )
    new_relation_memory(
        ctx,
        "[friendship] [friendship] Alpha is friends with Beta.",
        ["Alpha", "Beta"],
        "friendship",
    )
    new_gender_memory(ctx, "[gender] Alpha is a woman.", ["Alpha"])

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


def test_type_specific_retrieval_forwards_one_type_and_one_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=Session)
    inspect_terms = Mock(return_value=Page(count=0, rows=[]))
    monkeypatch.setattr(glossary_common.access, "inspect_terms", inspect_terms)

    result = fact_memories(
        _run_context(db),
        "Alpha",
        "species",
        term_search="human",
    )

    assert result == Page(count=0, rows=[])
    assert inspect_terms.call_args.args[3] == [MemoryType.FACT]
    assert inspect_terms.call_args.kwargs == {"marks": ["species"], "term_search": "human"}

    definition_memories(_run_context(db), "Alpha")
    assert inspect_terms.call_args.kwargs == {"marks": [None], "term_search": None}

    relation_memories(_run_context(db), "Alpha", "friendship")
    assert inspect_terms.call_args.args[3] == [MemoryType.RELATION]
    assert inspect_terms.call_args.kwargs == {"marks": ["friendship"], "term_search": None}

    gender_memories(_run_context(db), "Alpha")
    assert inspect_terms.call_args.args[3] == [MemoryType.FACT]
    assert inspect_terms.call_args.kwargs == {"marks": ["gender"], "term_search": None}


def test_advanced_gender_state_groups_namespaced_aspects(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=Session)
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
        Mock(return_value=Page(count=4, rows=[body, identity, presentation, change_rule])),
    )

    state = gender_state(_run_context(db), "Alpha")

    assert [row.memory.memory_content for row in state.body] == ["Alpha's current body is female."]
    assert [row.memory.memory_content for row in state.identity] == ["Alpha self-identifies as male."]
    assert [row.memory.memory_content for row in state.presentation] == ["Alpha ordinarily presents as a woman."]
    assert [row.memory.memory_content for row in state.change_rule] == ["Alpha changes body under moonlight."]


def test_advanced_gender_create_rejects_second_active_aspect(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=Session)
    monkeypatch.setattr(glossary_common.access, "inspect_terms", Mock(return_value=Page(count=1, rows=[])))

    with pytest.raises(ModelRetry, match="already has an active body memory"):
        new_gender_fact_memory(
            _run_context(db),
            "Alpha",
            "body",
            "Alpha's current body is female.",
        )


def test_advanced_gender_create_allows_multiple_change_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=Session)
    inspect_terms = Mock(return_value=Page(count=1, rows=[]))
    create_memory = Mock(return_value="m1")
    monkeypatch.setattr(glossary_common.access, "inspect_terms", inspect_terms)
    monkeypatch.setattr(glossary_common, "create_memory", create_memory)

    result = new_gender_fact_memory(
        _run_context(db),
        "Alpha",
        "change_rule",
        "Alpha changes body under moonlight.",
    )

    assert result == "m1"
    inspect_terms.assert_not_called()
    assert create_memory.call_args.args[6] == "gender.change_rule"


def test_gender_perception_tools_preserve_direction_and_namespaced_mark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock(spec=Session)
    inspect_terms = Mock(return_value=Page(count=0, rows=[]))
    create_memory = Mock(return_value="m1")
    monkeypatch.setattr(glossary_common.access, "inspect_terms", inspect_terms)
    monkeypatch.setattr(glossary_common, "create_memory", create_memory)

    result = gender_perception_memories(_run_context(db), "Observer", "Subject")
    assert result == Page(count=0, rows=[])
    assert inspect_terms.call_args.args[2] == ["Observer"]
    assert inspect_terms.call_args.kwargs == {
        "marks": ["gender.perception"],
        "term_search": "Subject",
    }

    handle = new_gender_perception_memory(
        _run_context(db),
        "Observer",
        "Subject",
        "Observer perceives Subject as a woman.",
    )
    assert handle == "m1"
    assert create_memory.call_args.args[2] == ["Observer", "Subject"]
    assert create_memory.call_args.args[3] == MemoryType.RELATION
    assert create_memory.call_args.args[6] == "gender.perception"


def test_job_params_reject_mixed_lightweight_and_advanced_gender_policies() -> None:
    with pytest.raises(
        ValidationError,
        match="glossary_gender_read and glossary_gender_advanced_facts_read cannot be selected together",
    ):
        JobParams(
            model_name="deepseek:deepseek-v4-flash-low",
            toolsets={
                "glossary_gender_read": {},
                "glossary_gender_advanced_facts_read": {},
            },
        )


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
