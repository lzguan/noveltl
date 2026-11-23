"""Memory-agent tasks on one event loop: real tasks, tools, and PostgreSQL; FunctionModel replaces inference."""

import asyncio
import itertools

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from src.memory.agent.config import JobParamsV1 as JobParams
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.stages import recording
from src.memory.agent.tasks import tasks as agent_tasks
from src.memory.agent.tasks.jobs import make_job
from src.memory.agent.toolsets.glossary.terms import glossary_term_toolset
from src.memory.models import MemoryChapterTask, MemoryJob
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.types import JobStatus
from test_support.database import run_with_async_session
from tests.memory.test_memory_agent_tasks import _make_memory_job

PARAMS = JobParams(model_name="deepseek:deepseek-v4-flash-low", toolsets={"glossary_terms": {}})


def _make_jobs(test_db: Session, job_count: int) -> list:
    _make_memory_job(test_db, chapter_count=job_count, params=PARAMS)
    memory_group_id = test_db.scalars(select(MemoryJob.memory_group_id)).one()
    return [
        run_with_async_session(
            test_db,
            lambda db, chapter_num=chapter_num: make_job(db, memory_group_id, chapter_num, chapter_num + 1, PARAMS),
        )
        for chapter_num in range(1, job_count + 1)
    ]


def _install_agent(monkeypatch: pytest.MonkeyPatch, engine: Engine | None = None) -> list[int]:
    """Record a term on the first request and finish on the second; note checked-out connections."""
    term_numbers = itertools.count()
    checked_out: list[int] = []

    async def respond(messages, _info: AgentInfo) -> ModelResponse:
        if engine is not None:
            assert isinstance(engine.pool, QueuePool)
            checked_out.append(engine.pool.checkedout())
        await asyncio.sleep(0.05)
        if len(messages) == 1:
            return ModelResponse(
                parts=[ToolCallPart("add_term", {"term_name": f"Term {next(term_numbers)}", "term_kind": "concept"})]
            )
        return ModelResponse(parts=[TextPart("Recorded.")])

    agent = Agent(FunctionModel(respond), deps_type=MemAgentDeps, toolsets=[glossary_term_toolset])
    monkeypatch.setattr(recording, "create_recording_agent", lambda *_: agent)
    return checked_out


async def _run_jobs(session_factory: sessionmaker[Session], job_ids: list) -> list[list]:
    async def run_job(job_id):
        return [task async for task in agent_tasks.run_all_tasks(session_factory, job_id)]

    return await asyncio.gather(*(run_job(job_id) for job_id in job_ids))


def test_no_connection_is_checked_out_while_the_model_is_requested(
    test_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    [job_id] = _make_jobs(test_db, 1)
    engine = create_engine(test_db.get_bind().engine.url, pool_size=2, max_overflow=0)
    checked_out = _install_agent(monkeypatch, engine)
    try:
        [completed] = asyncio.run(_run_jobs(sessionmaker(autoflush=False, bind=engine), [job_id]))
    finally:
        engine.dispose()

    assert len(completed) == 1
    assert checked_out == [0, 0]


def test_many_concurrent_tasks_complete_on_one_event_loop(test_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    job_count = 48
    job_ids = _make_jobs(test_db, job_count)
    _install_agent(monkeypatch)
    # Sized like the worker's engine: sync tools run in anyio's worker threads, one connection each.
    engine = create_engine(test_db.get_bind().engine.url, pool_size=40, max_overflow=0, pool_timeout=10)
    try:
        results = asyncio.run(_run_jobs(sessionmaker(autoflush=False, bind=engine), job_ids))
    finally:
        engine.dispose()

    assert [len(completed) for completed in results] == [1] * job_count
    statuses = test_db.scalars(
        select(MemoryChapterTask.task_status).where(MemoryChapterTask.memory_job_id.in_(job_ids))
    ).all()
    assert statuses == [JobStatus.COMPLETED] * job_count
    assert len(test_db.scalars(select(GlossaryTerm.term)).all()) == job_count
