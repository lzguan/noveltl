import logging
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from contextlib import aclosing
from dataclasses import dataclass
from datetime import timedelta

from pydantic_ai import AgentRunResult
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased, sessionmaker

from src.languages.models import Language
from src.memory.access import MemAccessContext
from src.memory.agent.capabilities.continuity import ContinuitySummaryOutput
from src.memory.agent.capabilities.conventions import ConventionsOutput
from src.memory.agent.capabilities.term_translation import TermTranslationOutput
from src.memory.agent.config import (
    RecordMemoriesStageConfig,
    StageConfig,
    SummarizeConventionsStageConfig,
    TranslateTermsStageConfig,
    job_params_adapter,
    resolve_stages,
)
from src.memory.agent.dependencies import MemAgentDeps
from src.memory.agent.stages.conventions import run_conventions_stage
from src.memory.agent.stages.recording import run_recording_stage
from src.memory.agent.stages.term_translation import run_term_translation_stage
from src.memory.agent.tasks.jobs import (
    claim_job,
    claim_next_task,
    claim_task,
    fail_task,
    refresh_job,
    release_job,
)
from src.memory.agent.tasks.schedule import TaskSchedule, get_schedule
from src.memory.exceptions import MemoryJobClaimLostException
from src.memory.models import MemoryChapterTask, MemoryGroup
from src.memory.shadow_models import MemoryWorkspace
from src.memory.types import JobStatus, StageName
from src.memory.workspaces import WorkspaceCommitUnknownError, discard_workspace, publish_workspace
from src.novels.models import Chapter, ChapterContent

logger = logging.getLogger(__name__)
DEFAULT_CLAIM_DURATION = timedelta(minutes=30)


@dataclass(frozen=True)
class ClaimedTask:
    memory_job_id: uuid.UUID
    chapter_id: uuid.UUID
    stage_num: int = 0


@dataclass(frozen=True)
class CompletedMemoryTask:
    memory_job_id: uuid.UUID
    memory_group_id: uuid.UUID
    chapter_id: uuid.UUID
    chapter_content_id: uuid.UUID
    chapter_num: int
    result: (
        AgentRunResult[str | ContinuitySummaryOutput]
        | AgentRunResult[ConventionsOutput]
        | AgentRunResult[TermTranslationOutput]
        | None
    )
    workspace_id: uuid.UUID
    stage_num: int = 0
    stage_name: StageName = "record_memories"


async def aiterate_tasks(
    db_factory: sessionmaker[Session],
    claim_token: uuid.UUID,
    claim_next_task: Callable[[Session, uuid.UUID], MemoryChapterTask | None],
) -> AsyncGenerator[ClaimedTask]:
    """
    Iterate over tasks, claiming each one.
    Caller should release task.
    """
    while True:
        with db_factory() as db:
            task = claim_next_task(db, claim_token)
            if task is None:
                return
            claimed_task = ClaimedTask(task.memory_job_id, task.chapter_id, task.stage_num)
        yield claimed_task


async def arun_tasks[T: CompletedMemoryTask](
    db_factory: sessionmaker[Session],
    claim_token: uuid.UUID,
    claim_next_task: Callable[[Session, uuid.UUID], MemoryChapterTask | None],
    process_task: Callable[[Session, ClaimedTask], Awaitable[T]],
) -> AsyncGenerator[T]:
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
                _complete_workspace_task(db, task, result, claim_token, db_factory)
        except MemoryJobClaimLostException:
            raise
        except Exception:
            logger.exception(
                "Memory task failed job_id=%s chapter_id=%s stage_num=%s",
                task.memory_job_id,
                task.chapter_id,
                task.stage_num,
            )
            try:
                with db_factory() as db:
                    released = fail_task(db, task.memory_job_id, task.chapter_id, claim_token, task.stage_num)
                if not released:
                    logger.warning(
                        "Could not mark memory task failed after losing its claim job_id=%s chapter_id=%s stage_num=%s",
                        task.memory_job_id,
                        task.chapter_id,
                        task.stage_num,
                    )
            except Exception:
                logger.exception(
                    "Could not mark memory task failed job_id=%s chapter_id=%s stage_num=%s",
                    task.memory_job_id,
                    task.chapter_id,
                    task.stage_num,
                )
            raise
        yield result


async def _run_single_task(
    db: Session,
    stages: Mapping[int, StageConfig],
    memory_group_id: uuid.UUID,
    task: ClaimedTask,
    lang_name: str,
) -> CompletedMemoryTask:
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
    ccid, cctext, cnum = db.execute(q).one()
    workspace = MemoryWorkspace(memory_job_id=task.memory_job_id, chapter_id=task.chapter_id, stage_num=task.stage_num)
    db.add(workspace)
    db.flush()
    workspace_id = workspace.workspace_id
    db.commit()
    context = MemAccessContext(memory_group_id, task.chapter_id, ccid, workspace_id)
    deps = MemAgentDeps(db, context)
    try:
        stage = stages[task.stage_num]
        match stage:
            case RecordMemoriesStageConfig():
                result = await run_recording_stage(deps, cctext, cnum, lang_name, stage)
            case SummarizeConventionsStageConfig():
                result = await run_conventions_stage(deps, cnum, lang_name, stage)
            case TranslateTermsStageConfig():
                result = await run_term_translation_stage(deps, cctext, cnum, lang_name, stage)
        db.commit()
        return CompletedMemoryTask(
            memory_job_id=task.memory_job_id,
            memory_group_id=memory_group_id,
            chapter_id=task.chapter_id,
            chapter_content_id=ccid,
            chapter_num=cnum,
            result=result,
            stage_num=task.stage_num,
            stage_name=stage.stage_name,
            workspace_id=workspace_id,
        )
    except BaseException:
        db.rollback()
        _cleanup_workspace(db, workspace_id)
        raise


def _cleanup_workspace(db: Session, workspace_id: uuid.UUID) -> None:
    try:
        discard_workspace(db, workspace_id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not clean up memory workspace workspace_id=%s", workspace_id)


def _complete_workspace_task(
    db: Session,
    task: ClaimedTask,
    result: CompletedMemoryTask,
    claim_token: uuid.UUID,
    db_factory: sessionmaker[Session],
) -> None:
    workspace_id = result.workspace_id
    try:
        publish_workspace(
            db,
            workspace_id,
            claim_token,
        )
    except WorkspaceCommitUnknownError:
        db.rollback()
        with db_factory() as verification:
            status = verification.scalar(
                select(MemoryChapterTask.task_status).where(
                    MemoryChapterTask.memory_job_id == task.memory_job_id,
                    MemoryChapterTask.chapter_id == task.chapter_id,
                    MemoryChapterTask.stage_num == task.stage_num,
                )
            )
        if status == JobStatus.COMPLETED:
            _cleanup_workspace(db, workspace_id)
            return
        _cleanup_workspace(db, workspace_id)
        raise
    except BaseException:
        db.rollback()
        _cleanup_workspace(db, workspace_id)
        raise
    _cleanup_workspace(db, workspace_id)


async def run_tasks(
    db_factory: sessionmaker[Session],
    memory_job_id: uuid.UUID,
    claim_next_task: Callable[[Session, uuid.UUID, TaskSchedule], MemoryChapterTask | None],
    *,
    claim_duration: timedelta = DEFAULT_CLAIM_DURATION,
) -> AsyncGenerator[CompletedMemoryTask]:
    """
    Claim a memory job and run tasks supplied by ``claim_next_task`` under the job's schedule.

    Pseudocode:

    Claim job and copy its configuration
    Fetch the memory group's language
    For each claimed task:
        Run and finalize the task
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
            params = job_params_adapter.validate_python(job.job_params)
            stages = dict(enumerate(resolve_stages(params)))
            schedule = get_schedule(params)
            lang_name = db.scalar(
                select(Language.language_name)
                .select_from(MemoryGroup)
                .join(Language, Language.language_code == MemoryGroup.memory_language)
                .where(MemoryGroup.memory_group_id == memory_group_id)
            )
            if lang_name is None:
                raise RuntimeError(f"Memory group {memory_group_id} has no configured language")

        async for completed_task in arun_tasks(
            db_factory,
            claim_token,
            lambda db, token: claim_next_task(db, token, schedule),
            lambda db, task: _run_single_task(db, stages, memory_group_id, task, lang_name),
        ):
            with db_factory() as db:
                if not refresh_job(db, memory_job_id, claim_token, claim_duration):
                    raise MemoryJobClaimLostException(f"Lost claim while refreshing memory job {memory_job_id}")
            yield completed_task
    finally:
        if owns_claim:
            with db_factory() as db:
                if not release_job(db, memory_job_id, claim_token):
                    logger.warning(
                        "Could not release memory job claim job_id=%s claim_token=%s",
                        memory_job_id,
                        claim_token,
                    )


async def run_one_task(
    db_factory: sessionmaker[Session],
    memory_job_id: uuid.UUID,
    chapter_id: uuid.UUID,
    stage_num: int = 0,
    *,
    claim_duration: timedelta = DEFAULT_CLAIM_DURATION,
) -> CompletedMemoryTask | None:
    """Run one pending chapter task, returning ``None`` when it cannot be claimed."""
    result = None
    async for task_result in run_tasks(
        db_factory,
        memory_job_id,
        lambda db, claim_token, schedule: claim_task(
            db, memory_job_id, chapter_id, claim_token, schedule, stage_num=stage_num
        ),
        claim_duration=claim_duration,
    ):
        result = task_result
    return result


async def run_all_tasks(
    db_factory: sessionmaker[Session],
    memory_job_id: uuid.UUID,
    *,
    claim_duration: timedelta = DEFAULT_CLAIM_DURATION,
) -> AsyncGenerator[CompletedMemoryTask]:
    """Run every pending chapter task in a job in chapter order."""
    async with aclosing(
        run_tasks(
            db_factory,
            memory_job_id,
            lambda db, claim_token, schedule: claim_next_task(db, memory_job_id, claim_token, schedule),
            claim_duration=claim_duration,
        )
    ) as tasks:
        async for result in tasks:
            yield result
