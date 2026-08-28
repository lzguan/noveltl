import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta

from pydantic_ai import Agent, AgentRunResult
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, sessionmaker

from src.languages.models import Language
from src.memory.access import MemAccessContext
from src.memory.agent.agent import create_agent, run_agent
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.tasks.jobs import (
    JobParams,
    claim_job,
    claim_next_task,
    claim_task,
    refresh_job,
    release_job,
    release_task,
)
from src.memory.exceptions import MemoryJobClaimLostException
from src.memory.models import MemoryChapterTask, MemoryGroup
from src.memory.types import JobStatus
from src.novels.models import Chapter, ChapterContent

logger = logging.getLogger(__name__)
DEFAULT_CLAIM_DURATION = timedelta(minutes=30)


@dataclass(frozen=True)
class ClaimedTask:
    memory_job_id: uuid.UUID
    chapter_id: uuid.UUID


async def aiterate_tasks(
    db_factory: sessionmaker[Session],
    claim_token: uuid.UUID,
    claim_next_task: Callable[[Session, uuid.UUID], MemoryChapterTask | None],
) -> AsyncIterator[ClaimedTask]:
    """
    Iterate over tasks, claiming each one.
    Caller should release task.
    """
    while True:
        with db_factory() as db:
            task = claim_next_task(db, claim_token)
            if task is None:
                return
            claimed_task = ClaimedTask(task.memory_job_id, task.chapter_id)
        yield claimed_task


async def arun_tasks[T](
    db_factory: sessionmaker[Session],
    claim_token: uuid.UUID,
    claim_next_task: Callable[[Session, uuid.UUID], MemoryChapterTask | None],
    process_task: Callable[[Session, ClaimedTask], Awaitable[T]],
) -> AsyncIterator[T]:
    """
    Pseudocode:

    For each task:
        Process task
        On failure, release with failure
        On success, release with success
    """
    async for task in aiterate_tasks(db_factory, claim_token, claim_next_task):
        try:
            with db_factory() as db:
                result = await process_task(db, task)
                if not release_task(db, task.memory_job_id, task.chapter_id, claim_token, JobStatus.COMPLETED):
                    raise MemoryJobClaimLostException(
                        f"Lost claim while completing memory task for chapter {task.chapter_id}"
                    )
        except MemoryJobClaimLostException:
            raise
        except Exception:
            try:
                with db_factory() as db:
                    released = release_task(
                        db,
                        task.memory_job_id,
                        task.chapter_id,
                        claim_token,
                        JobStatus.FAILED,
                    )
                if not released:
                    logger.warning(
                        "Could not mark memory task failed after losing its claim job_id=%s chapter_id=%s",
                        task.memory_job_id,
                        task.chapter_id,
                    )
            except Exception:
                logger.exception(
                    "Could not mark memory task failed job_id=%s chapter_id=%s",
                    task.memory_job_id,
                    task.chapter_id,
                )
            raise
        yield result


async def _run_single_task(
    db: Session,
    agent: Agent[MemAgentDeps, str],
    memory_group_id: uuid.UUID,
    task: ClaimedTask,
    lang_name: str,
) -> AgentRunResult[str]:
    # fetch chapter content and language
    cc_alias = aliased(ChapterContent)
    q = (
        select(ChapterContent.chapter_content_id, ChapterContent.chapter_content_text, Chapter.chapter_num)
        .select_from(Chapter)
        .where(Chapter.chapter_id == task.chapter_id)
        .join(ChapterContent, Chapter.chapter_id == ChapterContent.chapter_id)
        .where(
            ChapterContent.chapter_content_version
            == select(cc_alias.chapter_content_version)
            .where(cc_alias.chapter_id == Chapter.chapter_id)
            .order_by(cc_alias.chapter_content_version.desc())
            .limit(1)
            .scalar_subquery()
        )
    )
    ccid, cctext, cnum = db.execute(q).one()._t
    context = MemAccessContext(memory_group_id, task.chapter_id, ccid)
    deps = MemAgentDeps(db, context)
    return await run_agent(agent, deps, cctext, cnum, lang_name)


async def run_tasks(
    db_factory: sessionmaker[Session],
    memory_job_id: uuid.UUID,
    claim_next_task: Callable[[Session, uuid.UUID], MemoryChapterTask | None],
    *,
    claim_duration: timedelta = DEFAULT_CLAIM_DURATION,
) -> AsyncIterator[AgentRunResult[str]]:
    """
    Claim a memory job and run tasks supplied by ``claim_next_task``.

    Pseudocode:

    Claim job and copy its configuration
    Fetch the memory group's language
    Create one agent
    For each claimed task:
        Run and finalize the task
        Refresh the job claim
        Yield the agent result
    Release the job claim
    """
    claim_token = uuid.uuid4()
    owns_claim = False

    try:
        with db_factory() as db:
            job = claim_job(db, memory_job_id, claim_token, claim_duration)
            if job is None:
                return
            owns_claim = True
            memory_group_id = job.memory_group_id
            params = JobParams.model_validate(job.job_params)
            lang_name = db.scalar(
                select(Language.language_name)
                .select_from(MemoryGroup)
                .join(Language, Language.language_code == MemoryGroup.memory_language)
                .where(MemoryGroup.memory_group_id == memory_group_id)
            )
            if lang_name is None:
                raise RuntimeError(f"Memory group {memory_group_id} has no configured language")

        agent = create_agent(params.model_name, params.plugins)
        async with agent:
            async for result in arun_tasks(
                db_factory,
                claim_token,
                claim_next_task,
                lambda db, task: _run_single_task(db, agent, memory_group_id, task, lang_name),
            ):
                with db_factory() as db:
                    if not refresh_job(db, memory_job_id, claim_token, claim_duration):
                        raise MemoryJobClaimLostException(f"Lost claim while refreshing memory job {memory_job_id}")
                yield result
    finally:
        if owns_claim:
            with db_factory() as db:
                if not release_job(db, memory_job_id, claim_token):
                    logger.warning(
                        "Could not release memory job claim job_id=%s claim_token=%s",
                        memory_job_id,
                        claim_token,
                    )


async def run_task(
    db_factory: sessionmaker[Session],
    memory_job_id: uuid.UUID,
    chapter_id: uuid.UUID,
    *,
    claim_duration: timedelta = DEFAULT_CLAIM_DURATION,
) -> AgentRunResult[str] | None:
    """Run one pending chapter task, returning ``None`` when it cannot be claimed."""
    result = None
    async for task_result in run_tasks(
        db_factory,
        memory_job_id,
        lambda db, claim_token: claim_task(db, memory_job_id, chapter_id, claim_token),
        claim_duration=claim_duration,
    ):
        result = task_result
    return result


async def run_all_tasks(
    db_factory: sessionmaker[Session],
    memory_job_id: uuid.UUID,
    *,
    claim_duration: timedelta = DEFAULT_CLAIM_DURATION,
) -> AsyncIterator[AgentRunResult[str]]:
    """Run every pending chapter task in a job in chapter order."""
    async for result in run_tasks(
        db_factory,
        memory_job_id,
        lambda db, claim_token: claim_next_task(db, memory_job_id, claim_token),
        claim_duration=claim_duration,
    ):
        yield result
