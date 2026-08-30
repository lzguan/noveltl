from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.prompts.prompt import MEMORY_AGENT_PROMPT
from src.memory.agent.toolsets import glossary_common
from src.memory.agent.toolsets.glossary_events import GLOSSARY_EVENT_INSTRUCTIONS, glossary_event_toolset
from src.memory.agent.toolsets.glossary_terms import (
    GLOSSARY_TERM_INSTRUCTIONS,
    definition_memories,
    fact_memories,
    glossary_term_toolset,
    new_definition_memory,
    new_fact_memory,
    new_relation_memory,
    relation_memories,
)
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
    for instructions in (MEMORY_AGENT_PROMPT, GLOSSARY_TERM_INSTRUCTIONS, GLOSSARY_EVENT_INSTRUCTIONS):
        normalized_instructions = " ".join(instructions.split()).lower()
        assert (
            "keep every novel-specific term exactly as it appears in the original source language"
            in normalized_instructions
        )
        assert "never translate, romanize, or replace" in normalized_instructions

    assert "Correct: `赤岚司 guards the northern archive.`" in MEMORY_AGENT_PROMPT
    assert "Wrong: `Crimson Mist Bureau guards the northern archive.`" in MEMORY_AGENT_PROMPT
    assert "Wrong: `赤岚司守卫着北方档案馆。`" in MEMORY_AGENT_PROMPT


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


def test_glossary_tool_schemas_separate_term_memories_from_events() -> None:
    assert set(glossary_term_toolset.tools) == {
        "add_term",
        "definition_memories",
        "expire_term_memory",
        "fact_memories",
        "new_definition_memory",
        "new_fact_memory",
        "new_relation_memory",
        "relation_memories",
        "supersede_definition_memory",
        "supersede_fact_memory",
        "supersede_relation_memory",
    }
    assert set(glossary_event_toolset.tools) == {
        "term_event_memories",
        "new_term_event_memory",
        "supersede_term_event_memory",
    }

    event_schema = glossary_event_toolset.tools["term_event_memories"].function_schema.json_schema
    assert event_schema["properties"]["skip"] == {"default": 0, "minimum": 0, "type": "integer"}
    assert event_schema["properties"]["limit"] == {
        "default": 10,
        "maximum": 20,
        "minimum": 1,
        "type": "integer",
    }
    assert event_schema["properties"]["active_only"] == {"default": True, "type": "boolean"}

    for tool_name, required in (
        ("definition_memories", ["term_name"]),
        ("relation_memories", ["term_name", "category"]),
        ("fact_memories", ["term_name", "category"]),
    ):
        term_schema = glossary_term_toolset.tools[tool_name].function_schema.json_schema
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
    for tool_name, required in (
        ("new_definition_memory", ["content", "term_names"]),
        ("new_relation_memory", ["content", "term_names", "category"]),
        ("new_fact_memory", ["content", "term_names", "category"]),
        ("supersede_definition_memory", ["memory_id", "content"]),
        ("supersede_relation_memory", ["memory_id", "content", "category"]),
        ("supersede_fact_memory", ["memory_id", "content", "category"]),
    ):
        write_schema = glossary_term_toolset.tools[tool_name].function_schema.json_schema
        assert write_schema["required"] == required
        assert "memory_kind" not in write_schema["properties"]
        assert "memory_type" not in write_schema["properties"]

    for tool_name in ("new_definition_memory", "new_fact_memory"):
        term_names_schema = glossary_term_toolset.tools[tool_name].function_schema.json_schema["properties"][
            "term_names"
        ]
        assert term_names_schema["minItems"] == 1
        assert term_names_schema["maxItems"] == 1

    relation_term_names_schema = glossary_term_toolset.tools["new_relation_memory"].function_schema.json_schema[
        "properties"
    ]["term_names"]
    assert relation_term_names_schema["minItems"] == 2

    fact_schema = glossary_term_toolset.tools["new_fact_memory"].function_schema.json_schema
    assert fact_schema["properties"]["category"] == {"$ref": "#/$defs/FactCategory"}
    assert fact_schema["$defs"]["FactCategory"]["enum"] == [
        "gender",
        "age_stage",
        "species",
        "appearance",
        "cultivation_level",
        "trait",
        "ability",
        "limitation",
    ]
    relation_schema = glossary_term_toolset.tools["new_relation_memory"].function_schema.json_schema
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

    assert create_memory.call_args_list[0].args[5] == "Alpha is human."
    assert create_memory.call_args_list[0].args[7] == "species"
    assert create_memory.call_args_list[1].args[5] == "A personal name."
    assert create_memory.call_args_list[1].args[7] is None
    assert create_memory.call_args_list[2].args[5] == "Alpha is friends with Beta."
    assert create_memory.call_args_list[2].args[7] == "friendship"


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
    monkeypatch.setattr("src.memory.agent.toolsets.glossary_terms.access.inspect_terms", inspect_terms)

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
