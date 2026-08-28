from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets import glossary_common
from src.memory.agent.toolsets.glossary_events import glossary_event_toolset
from src.memory.agent.toolsets.glossary_terms import glossary_term_toolset
from src.memory.exceptions import GlossaryTermNotFoundException
from src.memory.types import MemoryType


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
        "term_memories",
        "new_term_memory",
        "supersede_term_memory",
    }
    assert set(glossary_event_toolset.tools) == {
        "term_event_memories",
        "new_term_event_memory",
        "supersede_term_event_memory",
    }

    for tool_name in ("term_memories", "new_term_memory", "supersede_term_memory"):
        schema = glossary_term_toolset.tools[tool_name].function_schema.json_schema
        assert schema["$defs"]["TermMemoryType"]["enum"] == ["def", "rel", "fact"]

    event_schema = glossary_event_toolset.tools["term_event_memories"].function_schema.json_schema
    assert event_schema["properties"]["skip"] == {"default": 0, "minimum": 0, "type": "integer"}
    assert event_schema["properties"]["limit"] == {
        "default": 10,
        "maximum": 20,
        "minimum": 1,
        "type": "integer",
    }
    assert event_schema["properties"]["active_only"] == {"default": True, "type": "boolean"}
