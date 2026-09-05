"""Related-category readers let curators find prior claims despite ambiguous classification.

The agent relies on combined filtering/counts before pagination to avoid missing
an existing relationship or occurrence and writing duplicate state.
"""

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary.gender_advanced_events import gender_event_memories
from src.memory.agent.toolsets.glossary.relations import RelationCategory, relation_memories
from src.memory.models import MemoryGroup
from src.memory.plugins.glossary import access
from src.memory.types import Creator, MemoryType
from test_support.test_data.scenarios import DatabaseScenario


@pytest.fixture
def related_context(test_db: Session, sample_scenario: DatabaseScenario) -> RunContext[MemAgentDeps]:
    group = MemoryGroup(
        memory_group_name="Related retrieval",
        novel_id=sample_scenario.novels["novel_1"].novel_id,
        memory_language="en",
    )
    test_db.add(group)
    test_db.flush()
    deps = MemAgentDeps(
        db=test_db,
        mem_access_context=MemAccessContext(
            memory_group_id=group.memory_group_id,
            chapter_id=sample_scenario.chapters["chapter_1"].chapter_id,
            chapter_content_id=sample_scenario.contents["chapter_1_v2"].chapter_content_id,
        ),
    )
    for name in ("Alpha", "Beta"):
        access.create_term(test_db, group.memory_group_id, name)
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


@pytest.mark.parametrize(
    "categories",
    [
        ("rank", "membership", "service", "organizational_hierarchy"),
        ("alliance", "commercial_partnership"),
    ],
)
def test_related_relations_share_filtered_pagination(
    related_context: RunContext[MemAgentDeps],
    categories: tuple[RelationCategory, ...],
) -> None:
    ctx = related_context
    for mark in (*categories, "friendship"):
        access.create_memory(
            ctx.deps.db,
            ctx.deps.mem_access_context,
            Creator.AGENT,
            MemoryType.RELATION,
            ["Alpha", "Beta"],
            f"Alpha and Beta have a formal {mark} relationship.",
            mark=mark,
        )
    access.create_memory(
        ctx.deps.db,
        ctx.deps.mem_access_context,
        Creator.AGENT,
        MemoryType.RELATION,
        ["Alpha", "Beta"],
        "An unrelated matching-category claim.",
        mark=categories[0],
    )
    ctx.deps.db.flush()

    combined = relation_memories(ctx, "Alpha", categories[0], term_search="FORMAL")
    assert combined.count == len(categories)
    assert {row.memory.mark for row in combined.rows} == set(categories)
    for category in categories:
        assert relation_memories(ctx, "Alpha", category, term_search="FORMAL") == combined
    pages = [
        relation_memories(ctx, "Alpha", category, skip=index, limit=1, term_search="FORMAL")
        for index, category in enumerate(categories)
    ]
    assert all(page.count == len(categories) for page in pages)
    assert [row for page in pages for row in page.rows] == combined.rows
    friendship = relation_memories(ctx, "Alpha", "friendship")
    assert friendship.count == 1
    assert friendship.rows[0].memory.mark == "friendship"


def test_body_swap_and_possession_share_pagination_without_other_events(
    related_context: RunContext[MemAgentDeps],
) -> None:
    ctx = related_context
    for kind in ("body_swap", "possession", "reveal", "transformation"):
        access.create_memory(
            ctx.deps.db,
            ctx.deps.mem_access_context,
            Creator.AGENT,
            MemoryType.EVENT,
            ["Alpha"],
            f"Alpha experienced {kind}.",
            mark=f"gender.event.{kind}",
        )
    ctx.deps.db.flush()

    combined = gender_event_memories(ctx, "Alpha", "body_swap")
    assert combined == gender_event_memories(ctx, "Alpha", "possession")
    assert combined.count == 2
    assert {row.memory.mark for row in combined.rows} == {"gender.event.body_swap", "gender.event.possession"}
    first = gender_event_memories(ctx, "Alpha", "possession", limit=1)
    second = gender_event_memories(ctx, "Alpha", "body_swap", skip=1, limit=1)
    assert first.count == second.count == 2
    assert first.rows + second.rows == combined.rows
    reveal = gender_event_memories(ctx, "Alpha", "reveal")
    assert reveal.count == 1
    assert reveal.rows[0].memory.mark == "gender.event.reveal"
