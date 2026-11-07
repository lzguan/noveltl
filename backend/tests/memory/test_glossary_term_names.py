from uuid import uuid4

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary.terms import add_term, normalize_agent_term_name
from src.memory.models import MemoryGroup
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.glossary.schemas import CreateGlossaryTerm, UpdateGlossaryTerm
from src.memory.plugins.glossary.types import TermKind
from test_support.test_data.scenarios import DatabaseScenario


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  白玫 ", "白玫"),
        ("【次元化身】", "次元化身"),
        ("「 次元化身 」", "次元化身"),
        ("“《魔法国度》”", "魔法国度"),
        # Marks inside the name are part of how the source writes it.
        ("‘花园’防卫战", "‘花园’防卫战"),
        ("【次元化身】天赋", "【次元化身】天赋"),
        # Mismatched or unpaired marks are left alone.
        ("【次元化身」", "【次元化身」"),
        ("【", "【"),
    ],
)
def test_agent_term_names_lose_only_whitespace_and_enclosing_marks(raw: str, expected: str) -> None:
    assert normalize_agent_term_name(raw) == expected


def test_user_term_names_are_only_trimmed() -> None:
    assert CreateGlossaryTerm(term="  【次元化身】 ").term == "【次元化身】"
    assert UpdateGlossaryTerm(term=" 白玫\n").term == "白玫"
    with pytest.raises(ValidationError):
        CreateGlossaryTerm(term="   ")


def test_agent_adds_the_normalized_term_and_rejects_names_that_normalize_to_nothing(
    test_db: Session, sample_scenario: DatabaseScenario
) -> None:
    group = MemoryGroup(
        novel_id=sample_scenario.novels["novel_1"].novel_id, memory_group_name="Term names", memory_language="en"
    )
    test_db.add(group)
    test_db.flush()
    ctx = RunContext(
        deps=MemAgentDeps(db=test_db, mem_access_context=MemAccessContext(group.memory_group_id, uuid4(), uuid4())),
        model=TestModel(),
        usage=RunUsage(),
    )

    assert add_term(ctx, "【次元化身】", TermKind.TECHNIQUE) == "Term 次元化身 added successfully."
    with pytest.raises(ModelRetry, match="already exists"):
        add_term(ctx, " 次元化身 ", TermKind.TECHNIQUE)
    with pytest.raises(ModelRetry, match="empty"):
        add_term(ctx, "“ ”", TermKind.OTHER)

    stored = test_db.scalars(select(GlossaryTerm.term).where(GlossaryTerm.memory_group_id == group.memory_group_id))
    assert list(stored) == ["次元化身"]
