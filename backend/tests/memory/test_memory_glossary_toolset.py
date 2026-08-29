from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets import glossary_common
from src.memory.agent.toolsets.glossary_events import glossary_event_toolset
from src.memory.agent.toolsets.glossary_terms import (
    DefinitionMemoryKind,
    FactMemoryKind,
    glossary_term_toolset,
    new_term_memory,
)
from src.memory.exceptions import GlossaryTermNotFoundException
from src.memory.plugins.glossary.schemas import AgentGlossaryMemory, AgentGlossaryTerm
from src.memory.plugins.glossary.types import FactCategory, TermKind
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
            "new_term_memory",
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
        "new_term_memory",
    )

    assert ctx.deps.uuid_cache.get_uuid(handle) == memory_id
    get_missing_term_names.assert_not_called()


def test_glossary_tool_schemas_separate_term_memories_from_events() -> None:
    assert set(glossary_term_toolset.tools) == {
        "add_term",
        "expire_term_memory",
        "term_memories",
        "new_term_memory",
        "supersede_term_memory",
    }
    assert set(glossary_event_toolset.tools) == {
        "term_event_memories",
        "new_term_event_memory",
        "supersede_term_event_memory",
    }

    term_memories_schema = glossary_term_toolset.tools["term_memories"].function_schema.json_schema
    assert term_memories_schema["$defs"]["TermMemoryType"]["enum"] == ["def", "rel", "fact"]

    event_schema = glossary_event_toolset.tools["term_event_memories"].function_schema.json_schema
    assert event_schema["properties"]["skip"] == {"default": 0, "minimum": 0, "type": "integer"}
    assert event_schema["properties"]["limit"] == {
        "default": 10,
        "maximum": 20,
        "minimum": 1,
        "type": "integer",
    }
    assert event_schema["properties"]["active_only"] == {"default": True, "type": "boolean"}

    term_schema = glossary_term_toolset.tools["term_memories"].function_schema.json_schema
    assert term_schema["properties"]["skip"] == {"default": 0, "minimum": 0, "type": "integer"}
    assert term_schema["properties"]["limit"] == {
        "default": 10,
        "maximum": 20,
        "minimum": 1,
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
    for tool_name, required in (
        ("new_term_memory", ["content", "term_names", "memory_kind"]),
        ("supersede_term_memory", ["memory_id", "content", "memory_kind"]),
    ):
        write_schema = glossary_term_toolset.tools[tool_name].function_schema.json_schema
        assert write_schema["required"] == required
        assert write_schema["$defs"]["TermMemoryKind"]["discriminator"] == {
            "mapping": {
                "def": "#/$defs/DefinitionMemoryKind",
                "fact": "#/$defs/FactMemoryKind",
                "rel": "#/$defs/RelationMemoryKind",
            },
            "propertyName": "memory_type",
        }
        assert write_schema["$defs"]["DefinitionMemoryKind"]["required"] == ["memory_type"]
        assert write_schema["$defs"]["RelationMemoryKind"]["required"] == ["memory_type"]
        assert write_schema["$defs"]["FactMemoryKind"]["required"] == ["memory_type", "category"]

    new_memory_schema = glossary_term_toolset.tools["new_term_memory"].function_schema.json_schema
    assert new_memory_schema["$defs"]["FactCategory"]["enum"] == [
        "gender",
        "age_stage",
        "species",
        "appearance",
        "cultivation_level",
        "trait",
        "ability",
        "limitation",
    ]


def test_fact_write_persists_category_marker_and_definition_content_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock(spec=Session)
    create_memory = Mock(return_value=(Mock(memory_id=uuid4()), []))
    monkeypatch.setattr(glossary_common.access, "create_memory", create_memory)
    ctx = _run_context(db)

    new_term_memory(
        ctx,
        "Alpha is human.",
        ["Alpha"],
        FactMemoryKind(memory_type=MemoryType.FACT, category=FactCategory.SPECIES),
    )
    new_term_memory(
        ctx,
        "A personal name.",
        ["Alpha"],
        DefinitionMemoryKind(memory_type=MemoryType.DEFINITION),
    )

    assert create_memory.call_args_list[0].args[5] == "[species] Alpha is human."
    assert create_memory.call_args_list[1].args[5] == "A personal name."


def test_retrieval_tool_result_serializes_agent_models_with_snake_case() -> None:
    result = Page[AgentGlossaryMemory[str]](
        count=1,
        rows=[
            AgentGlossaryMemory[str](
                memory=AgentMemory[str](
                    memory_id="m1",
                    memory_type=MemoryType.FACT,
                    memory_content="[species] Alpha is human.",
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
        tool_name="term_memories",
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
                    "memory_content": "[species] Alpha is human.",
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
