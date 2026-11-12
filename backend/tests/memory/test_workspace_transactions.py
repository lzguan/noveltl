import asyncio

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.capabilities import AbstractCapability, Toolset
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.memory.agent.capabilities.conventions import ConventionsOutput, write_conventions_output
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.toolsets.glossary.context import initial_glossary_context
from src.memory.agent.toolsets.glossary.definitions import glossary_definitions_write_toolset
from src.memory.agent.toolsets.glossary.terms import glossary_term_toolset
from src.memory.agent.transactions import tool_transaction
from src.memory.models import Memory
from src.memory.plugins.glossary import access
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.shadow_models import ShadowConvention, ShadowMemory, ShadowTerm
from tests.fixtures.memory_workspaces import ReadScenario
from tests.fixtures.memory_workspaces import reads as reads


def test_tools_commit_drafts_and_model_requests_have_no_open_transaction(test_db: Session, reads: ReadScenario):
    observations = []

    def respond(_messages, _info):
        assert not test_db.in_transaction()
        with Session(bind=test_db.get_bind()) as other:
            observations.append(
                (
                    other.scalar(select(func.count()).select_from(ShadowTerm)),
                    other.scalar(select(func.count()).select_from(ShadowMemory)),
                )
            )
            assert other.scalar(select(func.count()).select_from(GlossaryTerm)) == 0
            assert other.scalar(select(func.count()).select_from(Memory)) == 0
        if len(observations) == 1:
            return ModelResponse(parts=[ToolCallPart("add_term", {"term_name": "Alpha", "term_kind": "concept"})])
        if len(observations) == 2:
            return ModelResponse(
                parts=[ToolCallPart("new_definition_memory", {"term_names": ["Alpha"], "content": "Draft definition."})]
            )
        return ModelResponse(parts=[TextPart("Done.")])

    agent = Agent(
        FunctionModel(respond),
        deps_type=MemAgentDeps,
        instructions=initial_glossary_context,
        capabilities=[
            Toolset(glossary_term_toolset),
            Toolset(glossary_definitions_write_toolset),
        ],
    )
    test_db.commit()
    asyncio.run(agent.run("Record context.", deps=MemAgentDeps(test_db, reads.current)))
    assert observations == [(0, 0), (1, 0), (1, 1)]
    assert not test_db.in_transaction()


def test_tool_retry_rolls_back_its_uncommitted_writes_before_next_model_request(test_db: Session, reads: ReadScenario):
    calls = 0

    def respond(_messages, _info):
        nonlocal calls
        assert not test_db.in_transaction()
        calls += 1
        if calls == 1:
            return ModelResponse(parts=[ToolCallPart("fail_after_write", {})])
        with Session(bind=test_db.get_bind()) as other:
            assert other.scalar(select(func.count()).select_from(ShadowTerm)) == 0
        return ModelResponse(parts=[TextPart("Continue without the failed write.")])

    agent = Agent(
        FunctionModel(respond),
        deps_type=MemAgentDeps,
    )

    @agent.tool(sequential=True)
    @tool_transaction
    def fail_after_write(ctx: RunContext[MemAgentDeps]) -> str:
        access.create_term(
            ctx.deps.db,
            ctx.deps.mem_access_context.memory_group_id,
            "Alpha",
            workspace_id=ctx.deps.mem_access_context.workspace_id,
        )
        raise ModelRetry("Retry without this write.")

    test_db.commit()
    asyncio.run(agent.run("Record context.", deps=MemAgentDeps(test_db, reads.current)))
    assert calls == 2
    assert not test_db.in_transaction()


def test_output_validator_commits_before_after_run_hooks(test_db: Session, reads: ReadScenario):
    observed = []

    class ObserveOutput(AbstractCapability[MemAgentDeps]):
        async def after_run(self, ctx, *, result):
            assert not ctx.deps.db.in_transaction()
            with Session(bind=test_db.get_bind()) as other:
                observed.append(other.scalar(select(func.count()).select_from(ShadowConvention)))
            return result

    def respond(_messages, info):
        assert not test_db.in_transaction()
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {"create": [{"category": "naming", "title": "Forms", "rule": "Preserve forms."}]},
                )
            ]
        )

    agent = Agent(
        FunctionModel(respond),
        deps_type=MemAgentDeps,
        output_type=ConventionsOutput,
        capabilities=[ObserveOutput()],
    )
    agent.output_validator(write_conventions_output)
    test_db.commit()
    asyncio.run(agent.run("Find conventions.", deps=MemAgentDeps(test_db, reads.current)))
    assert observed == [1]
