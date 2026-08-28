from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets import glossary
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


def test_new_memory_diagnoses_missing_terms_only_after_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=Session)
    create_memory = Mock(side_effect=GlossaryTermNotFoundException("Some terms do not exist."))
    get_missing_term_names = Mock(return_value=["金虚宫"])
    monkeypatch.setattr(glossary.access, "create_memory", create_memory)
    monkeypatch.setattr(glossary.access, "get_missing_term_names", get_missing_term_names)

    with pytest.raises(ModelRetry, match=r'Missing glossary terms: \["金虚宫"\]'):
        glossary._new_memory(
            _run_context(db),
            "A memory.",
            ["金虚宫", "炽焰山"],
            MemoryType.DEFINITION,
        )

    get_missing_term_names.assert_called_once()


def test_new_memory_skips_missing_term_query_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock(spec=Session)
    memory_id = uuid4()
    create_memory = Mock(return_value=(Mock(memory_id=memory_id), []))
    get_missing_term_names = Mock()
    monkeypatch.setattr(glossary.access, "create_memory", create_memory)
    monkeypatch.setattr(glossary.access, "get_missing_term_names", get_missing_term_names)

    assert glossary._new_memory(_run_context(db), "A memory.", ["金虚宫"], MemoryType.DEFINITION) == memory_id
    get_missing_term_names.assert_not_called()


def test_term_memories_forwards_multiple_memory_types(monkeypatch: pytest.MonkeyPatch) -> None:
    memory_types = [MemoryType.RELATION, MemoryType.FACT]
    term_memories = Mock(return_value=[])
    monkeypatch.setattr(glossary, "_term_memories", term_memories)
    ctx = _run_context(MagicMock(spec=Session))

    assert glossary.term_memories(ctx, ["白蛇", "于蓉"], memory_types) == []
    term_memories.assert_called_once_with(ctx, ["白蛇", "于蓉"], memory_types)
