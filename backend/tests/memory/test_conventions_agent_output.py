import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext, RunUsage
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from sqlalchemy.orm import Session

from src.memory.access import MemAccessContext
from src.memory.agent.capabilities.conventions import ConventionsOutput, write_conventions_output
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.models import MemoryGroup
from src.memory.plugins.conventions.access import create_convention, read_conventions
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.types import Creator, ReviewStatus
from test_support.test_data.scenarios import DatabaseScenario


def _group_with_conventions(db: Session, scenario: DatabaseScenario) -> tuple[MemAgentDeps, dict[str, str]]:
    """Ranks and Places are agent drafts, Codenames is approved and user-written; handles keyed by title."""
    group = MemoryGroup(
        novel_id=scenario.novels["novel_1"].novel_id, memory_group_name="Conventions", memory_language="en"
    )
    db.add(group)
    db.flush()
    for title, creator in [("Ranks", Creator.AGENT), ("Codenames", Creator.USER), ("Places", Creator.AGENT)]:
        row = create_convention(
            db,
            group.memory_group_id,
            category=ConventionCategory.NAMING,
            title=title,
            rule=f"{title} rule",
            rationale=None,
            creator_type=creator,
        )
        if title == "Codenames":
            row.review_status = ReviewStatus.APPROVED
    db.commit()
    deps = MemAgentDeps(db=db, mem_access_context=MemAccessContext(group.memory_group_id, uuid4(), uuid4()))
    # Hand out handles as the context builder will.
    handles = {
        row.title: deps.convention_handles.new(row.convention_id) for row in read_conventions(db, group.memory_group_id)
    }
    return deps, handles


def _ctx(deps: MemAgentDeps) -> RunContext[MemAgentDeps]:
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def _stored(db: Session, deps: MemAgentDeps) -> dict[str, tuple[str, Creator, ReviewStatus]]:
    db.expire_all()
    return {
        row.title: (row.rule, row.creator_type, row.review_status)
        for row in read_conventions(db, deps.mem_access_context.memory_group_id)
    }


UNCHANGED = {
    "Ranks": ("Ranks rule", Creator.AGENT, ReviewStatus.PENDING),
    "Codenames": ("Codenames rule", Creator.USER, ReviewStatus.APPROVED),
    "Places": ("Places rule", Creator.AGENT, ReviewStatus.PENDING),
}


def test_output_rejects_a_handle_used_twice_and_blank_text() -> None:
    with pytest.raises(ValidationError, match="at most once"):
        ConventionsOutput.model_validate(
            {"revise": [{"handle": "c1", "category": "naming", "title": "T", "rule": "R"}], "withdraw": ["c1"]}
        )
    with pytest.raises(ValidationError):
        ConventionsOutput.model_validate({"create": [{"category": "naming", "title": "  ", "rule": "R"}]})
    draft = ConventionsOutput.model_validate(
        {"create": [{"category": "naming", "title": " Ranks ", "rule": " Use -rank. "}]}
    ).create[0]
    assert (draft.title, draft.rule, draft.rationale) == ("Ranks", "Use -rank.", None)


def test_writes_creates_revisions_and_withdrawals_of_agent_drafts(
    test_db: Session, sample_scenario: DatabaseScenario
) -> None:
    deps, h = _group_with_conventions(test_db, sample_scenario)
    output = ConventionsOutput.model_validate(
        {
            "create": [
                {"category": "naming", "title": "Seed ladder", "rule": "Egg/Pupa/Seed-rank."},
                {"category": "style", "title": "Status panels", "rule": "Keep 【…】 as [ … ]."},
            ],
            "revise": [
                {"handle": h["Ranks"], "category": "style", "title": "Ranks", "rule": "Use -rank for every grade."}
            ],
            "withdraw": [h["Places"]],
        }
    )

    assert write_conventions_output(_ctx(deps), output) is output

    assert _stored(test_db, deps) == {
        "Ranks": ("Use -rank for every grade.", Creator.AGENT, ReviewStatus.PENDING),
        "Codenames": UNCHANGED["Codenames"],
        "Seed ladder": ("Egg/Pupa/Seed-rank.", Creator.AGENT, ReviewStatus.PENDING),
        "Status panels": ("Keep 【…】 as [ … ].", Creator.AGENT, ReviewStatus.PENDING),
    }
    categories = {row.title: row.category for row in read_conventions(test_db, deps.mem_access_context.memory_group_id)}
    assert categories["Status panels"] == categories["Ranks"] == ConventionCategory.STYLE


@pytest.mark.parametrize(
    ("bad_target", "message"),
    [("c9", "Unknown convention handles: c9"), ("Codenames", "are approved, rejected, or user-written")],
)
def test_an_unknown_or_locked_handle_rolls_back_the_whole_attempt(
    test_db: Session, sample_scenario: DatabaseScenario, bad_target: str, message: str
) -> None:
    deps, h = _group_with_conventions(test_db, sample_scenario)
    output = ConventionsOutput.model_validate(
        {
            "create": [{"category": "naming", "title": "Seed ladder", "rule": "Egg/Pupa/Seed-rank."}],
            "revise": [{"handle": h["Ranks"], "category": "naming", "title": "Ranks", "rule": "Changed."}],
            "withdraw": [h.get(bad_target, bad_target)],
        }
    )

    with pytest.raises(ModelRetry, match=message):
        write_conventions_output(_ctx(deps), output)

    assert _stored(test_db, deps) == UNCHANGED


def test_a_draft_approved_after_the_context_was_built_is_locked(
    test_db: Session, sample_scenario: DatabaseScenario
) -> None:
    deps, h = _group_with_conventions(test_db, sample_scenario)
    ranks = test_db.get(TranslationConvention, deps.convention_handles.get_uuid(h["Ranks"]))
    assert ranks is not None
    ranks.review_status = ReviewStatus.APPROVED
    test_db.commit()

    with pytest.raises(ModelRetry, match=f"{h['Ranks']} are approved"):
        write_conventions_output(_ctx(deps), ConventionsOutput(withdraw=[h["Ranks"]]))


def test_agent_retries_after_a_rejected_attempt_and_only_the_retry_is_saved(
    test_db: Session, sample_scenario: DatabaseScenario
) -> None:
    """FunctionModel stands in for inference; validation, retries, and writes are real."""
    deps, h = _group_with_conventions(test_db, sample_scenario)
    calls = 0

    def respond(messages, info: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        output = {
            "create": [{"category": "naming", "title": "Seed ladder", "rule": "Egg/Pupa/Seed-rank."}],
            "withdraw": [h["Codenames"]] if calls == 1 else [h["Places"]],
        }
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])

    agent = Agent(FunctionModel(respond), deps_type=MemAgentDeps, output_type=ConventionsOutput)
    agent.output_validator(write_conventions_output)

    result = asyncio.run(agent.run("Summarize conventions.", deps=deps))

    assert calls == 2
    feedback = [
        str(part.content)
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    assert len(feedback) == 2 and "Nothing from this attempt was saved" in feedback[0]
    # The first attempt's create was rolled back, so the convention exists once.
    assert _stored(test_db, deps) == {
        "Ranks": UNCHANGED["Ranks"],
        "Codenames": UNCHANGED["Codenames"],
        "Seed ladder": ("Egg/Pupa/Seed-rank.", Creator.AGENT, ReviewStatus.PENDING),
    }
