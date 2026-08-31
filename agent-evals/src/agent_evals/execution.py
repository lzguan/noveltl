import asyncio
import json
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic_ai import capture_run_messages
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.usage import RunUsage
from src.datasets import load_catalog, load_novel
from src.datasets.domain import NovelDataset
from src.datasets.materializer import make_novel, materialize_novel_contents
from src.languages.models import Language
from src.memory.agent.agent import create_agent, run_novel
from src.memory.agent.tasks.jobs import JobParams
from src.memory.models import Memory, MemoryGroup
from src.memory.plugins.glossary.models import GlossaryAssociation, GlossaryTerm
from src.novels.models import SourceWork

from agent_evals.corpora import inspect_corpus, resolve_corpus
from agent_evals.database import TemporaryPostgresDatabase, temporary_postgres_database
from agent_evals.progress import RunProgress, RunStatus
from agent_evals.run_configs import load_run_config
from agent_evals.schemas import RunConfig
from agent_evals.storage import EvalWorkspace, dump_yaml_model

ReplicaExecutor = Callable[["RunContext", int, Path], Awaitable["ReplicaResult"]]


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_path: Path
    config: RunConfig
    dataset: NovelDataset
    database_url: str
    budget: "BudgetController"
    report_progress: Callable[["RunProgress"], None]


@dataclass(frozen=True)
class ReplicaResult:
    index: int
    status: RunStatus
    completed_chapters: tuple[int, ...]
    usage: RunUsage
    failure: dict[str, object] | None = None


@dataclass(frozen=True)
class RunResult:
    run_id: str
    path: Path
    status: RunStatus


class BudgetController:
    def __init__(self, max_cost_usd: Decimal | None, max_wall_seconds: int | None) -> None:
        self.max_cost_usd = max_cost_usd
        self.deadline = time.monotonic() + max_wall_seconds if max_wall_seconds is not None else None
        self.cost_usd = Decimal(0)
        self._lock = asyncio.Lock()

    async def stop_reason(self) -> str | None:
        async with self._lock:
            if self.deadline is not None and time.monotonic() >= self.deadline:
                return "maximum wall time reached"
            if self.max_cost_usd is not None and self.cost_usd >= self.max_cost_usd:
                return "maximum cost reached"
            return None

    async def add_usage(self, usage: RunUsage) -> Decimal:
        async with self._lock:
            if usage.cost is not None:
                self.cost_usd += usage.cost
            return self.cost_usd


def _ignore_progress(progress: RunProgress) -> None:
    pass


def resolve_database_url() -> str:
    value = os.getenv("AGENT_EVAL_DATABASE_URL") or os.getenv("DB_URL")
    if not value:
        raise RuntimeError("Set AGENT_EVAL_DATABASE_URL to a PostgreSQL URL that may create temporary databases")
    return value


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _serialize_usage(usage: RunUsage) -> dict[str, Any]:
    return {
        "requests": usage.requests,
        "toolCalls": usage.tool_calls,
        "inputTokens": usage.input_tokens,
        "outputTokens": usage.output_tokens,
        "cacheWriteTokens": usage.cache_write_tokens,
        "cacheReadTokens": usage.cache_read_tokens,
        "totalTokens": usage.total_tokens,
        "costUsd": str(usage.cost) if usage.cost is not None else None,
        "details": usage.details,
    }


def _serialize_exception(exc: BaseException) -> dict[str, object]:
    value: dict[str, object] = {"type": type(exc).__name__, "message": str(exc)}
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            details = errors(include_input=True)
        except TypeError:
            details = errors()
        value["errors"] = json.loads(json.dumps(details, ensure_ascii=False, default=str))
    return value


def _serialize_failure(exc: BaseException, chapter_num: int | None = None) -> dict[str, object]:
    failure = _serialize_exception(exc)
    if chapter_num is not None:
        failure["chapterNum"] = chapter_num
    causes: list[dict[str, object]] = []
    seen = {id(exc)}
    cause = exc.__cause__ if exc.__cause__ is not None else exc.__context__
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        causes.append(_serialize_exception(cause))
        cause = cause.__cause__ if cause.__cause__ is not None else cause.__context__
    if causes:
        failure["causes"] = causes
    return failure


def _language_name(code: str) -> str:
    return {"en": "English", "zh": "Chinese", "ja": "Japanese", "ko": "Korean"}.get(code, code)


def _seed_database(
    database: TemporaryPostgresDatabase, dataset: NovelDataset, index: int
) -> tuple[uuid.UUID, uuid.UUID]:
    with database.session_factory() as db:
        source_language = Language(
            language_name=_language_name(dataset.language_code), language_code=dataset.language_code
        )
        db.add(source_language)
        if dataset.language_code != "en":
            db.add(Language(language_name="English", language_code="en"))
        source_work = SourceWork(source_work_title=dataset.title)
        db.add(source_work)
        db.flush()
        novel = make_novel(dataset, source_work)
        db.add(novel)
        db.flush()
        materialize_novel_contents(db, dataset, novel)
        memory_group = MemoryGroup(
            memory_group_name=f"Agent eval replica {index}",
            novel_id=novel.novel_id,
            memory_language="en",
        )
        db.add(memory_group)
        db.commit()
        return novel.novel_id, memory_group.memory_group_id


def _snapshot_memory(db: Any, memory_group_id: uuid.UUID) -> dict[str, object]:
    terms = (
        db.query(GlossaryTerm)
        .filter(GlossaryTerm.memory_group_id == memory_group_id)
        .order_by(GlossaryTerm.term, GlossaryTerm.term_id)
        .all()
    )
    memories = (
        db.query(Memory)
        .filter(Memory.memory_group_id == memory_group_id)
        .order_by(Memory.memory_start_num, Memory.created_at, Memory.memory_id)
        .all()
    )
    associations = (
        db.query(GlossaryAssociation)
        .join(Memory, Memory.memory_id == GlossaryAssociation.memory_id)
        .filter(Memory.memory_group_id == memory_group_id)
        .order_by(GlossaryAssociation.term_id, GlossaryAssociation.memory_id)
        .all()
    )
    return {
        "terms": [
            {
                "termId": str(term.term_id),
                "term": term.term,
                "termKind": term.term_kind.value if term.term_kind is not None else None,
                "reviewStatus": term.review_status.value,
                "createdAt": term.created_at.isoformat(),
                "updatedAt": term.updated_at.isoformat(),
            }
            for term in terms
        ],
        "memories": [
            {
                "memoryId": str(memory.memory_id),
                "memoryType": memory.memory_type.value,
                "mark": memory.mark,
                "observedIn": str(memory.memory_observed_in),
                "startNum": memory.memory_start_num,
                "endNum": memory.memory_end_num,
                "supersedesMemoryId": (
                    str(memory.supersedes_memory_id) if memory.supersedes_memory_id is not None else None
                ),
                "content": memory.memory_content,
                "reviewStatus": memory.memory_review_status.value,
                "creatorType": memory.creator_type.value,
                "pluginName": memory.plugin_name,
                "createdAt": memory.created_at.isoformat(),
                "updatedAt": memory.updated_at.isoformat(),
            }
            for memory in memories
        ],
        "associations": [
            {"termId": str(association.term_id), "memoryId": str(association.memory_id)} for association in associations
        ],
    }


def _replica_manifest(
    result: ReplicaResult,
    *,
    started_at: datetime,
    finished_at: datetime | None,
    database_name: str | None,
) -> dict[str, object]:
    return {
        "status": result.status,
        "replica": result.index,
        "database": database_name,
        "startedAt": started_at.isoformat(),
        "finishedAt": finished_at.isoformat() if finished_at is not None else None,
        "completedChapters": list(result.completed_chapters),
        "usage": _serialize_usage(result.usage),
        "failure": result.failure,
    }


async def execute_live_replica(context: RunContext, index: int, replica_dir: Path) -> ReplicaResult:
    started_at = _utc_now()
    usage = RunUsage()
    completed: list[int] = []
    database_name: str | None = None
    result = ReplicaResult(index=index, status="running", completed_chapters=(), usage=usage)
    _write_json(
        replica_dir / "replica.json",
        _replica_manifest(result, started_at=started_at, finished_at=None, database_name=None),
    )

    try:
        with temporary_postgres_database(context.database_url) as database:
            database_name = database.name
            novel_id, memory_group_id = _seed_database(database, context.dataset, index)
            params = JobParams.model_validate(
                {
                    "model_name": context.config.agent.model_name,
                    "toolsets": [toolset.name for toolset in context.config.agent.toolsets],
                }
            )
            agent = create_agent(params.model_name, params.toolsets)
            try:
                async with agent:
                    for chapter in context.dataset.chapters:
                        stop_reason = await context.budget.stop_reason()
                        if stop_reason is not None:
                            result = ReplicaResult(
                                index=index,
                                status="budget_exceeded",
                                completed_chapters=tuple(completed),
                                usage=usage,
                                failure={"type": "BudgetExceeded", "message": stop_reason},
                            )
                            break
                        for attempt in range(1, context.config.execution.retries_per_chapter + 2):
                            attempt_started = _utc_now()
                            with capture_run_messages() as messages:
                                try:
                                    iterator = run_novel(
                                        database.session_factory,
                                        agent,
                                        novel_id,
                                        memory_group_id,
                                        start_chapter_num=chapter.number,
                                        end_chapter_num=chapter.number + 1,
                                    )
                                    chapter_num, chapter_result = await anext(aiter(iterator))
                                except Exception as exc:
                                    attempt_finished = _utc_now()
                                    failure = _serialize_failure(exc, chapter.number)
                                    _write_json(
                                        replica_dir
                                        / "chapters"
                                        / f"chapter-{chapter.number:04d}-attempt-{attempt:02d}.json",
                                        {
                                            "status": "failed",
                                            "chapterNum": chapter.number,
                                            "attempt": attempt,
                                            "startedAt": attempt_started.isoformat(),
                                            "finishedAt": attempt_finished.isoformat(),
                                            "durationSeconds": (attempt_finished - attempt_started).total_seconds(),
                                            "failure": failure,
                                            "messages": json.loads(ModelMessagesTypeAdapter.dump_json(messages)),
                                        },
                                    )
                                    context.report_progress(
                                        RunProgress(
                                            kind="chapter_failed",
                                            run_id=context.run_id,
                                            run_path=context.run_path,
                                            replica=index,
                                            chapter_num=chapter.number,
                                            attempt=attempt,
                                            message=str(exc),
                                        )
                                    )
                                    if attempt > context.config.execution.retries_per_chapter:
                                        result = ReplicaResult(
                                            index=index,
                                            status="failed",
                                            completed_chapters=tuple(completed),
                                            usage=usage,
                                            failure=failure,
                                        )
                                    continue

                            attempt_finished = _utc_now()
                            chapter_usage: Any = chapter_result.usage
                            usage.incr(chapter_usage)
                            run_cost = await context.budget.add_usage(chapter_usage)
                            completed.append(chapter_num)
                            _write_json(
                                replica_dir / "chapters" / f"chapter-{chapter_num:04d}-attempt-{attempt:02d}.json",
                                {
                                    "status": "completed",
                                    "chapterNum": chapter_num,
                                    "attempt": attempt,
                                    "startedAt": attempt_started.isoformat(),
                                    "finishedAt": attempt_finished.isoformat(),
                                    "durationSeconds": (attempt_finished - attempt_started).total_seconds(),
                                    "agentRunId": chapter_result.run_id,
                                    "output": chapter_result.output,
                                    "usage": _serialize_usage(chapter_usage),
                                    "messages": json.loads(chapter_result.all_messages_json()),
                                },
                            )
                            context.report_progress(
                                RunProgress(
                                    kind="chapter_completed",
                                    run_id=context.run_id,
                                    run_path=context.run_path,
                                    replica=index,
                                    chapter_num=chapter_num,
                                    attempt=attempt,
                                    replica_cost_usd=usage.cost,
                                    run_cost_usd=run_cost,
                                )
                            )
                            result = ReplicaResult(
                                index=index,
                                status="running",
                                completed_chapters=tuple(completed),
                                usage=usage,
                            )
                            _write_json(
                                replica_dir / "replica.json",
                                _replica_manifest(
                                    result,
                                    started_at=started_at,
                                    finished_at=None,
                                    database_name=database_name,
                                ),
                            )
                            break
                        if result.status == "failed":
                            break
                    else:
                        result = ReplicaResult(
                            index=index,
                            status="completed",
                            completed_chapters=tuple(completed),
                            usage=usage,
                        )
            finally:
                with database.session_factory() as db:
                    _write_json(replica_dir / "memory.json", _snapshot_memory(db, memory_group_id))
    except asyncio.CancelledError:
        result = ReplicaResult(
            index=index,
            status="interrupted",
            completed_chapters=tuple(completed),
            usage=usage,
            failure={"type": "CancelledError", "message": "evaluation interrupted"},
        )
    except Exception as exc:
        result = ReplicaResult(
            index=index,
            status="failed",
            completed_chapters=tuple(completed),
            usage=usage,
            failure=_serialize_failure(exc),
        )
    finally:
        _write_json(
            replica_dir / "replica.json",
            _replica_manifest(result, started_at=started_at, finished_at=_utc_now(), database_name=database_name),
        )
    return result


def _overall_status(results: list[ReplicaResult]) -> RunStatus:
    statuses = {result.status for result in results}
    if "interrupted" in statuses:
        return "interrupted"
    if "failed" in statuses:
        return "failed"
    if "budget_exceeded" in statuses:
        return "budget_exceeded"
    return "completed"


async def run_evaluation(
    workspace: EvalWorkspace,
    config_value: str | Path,
    *,
    database_url: str | None = None,
    replica_executor: ReplicaExecutor = execute_live_replica,
    progress_reporter: Callable[[RunProgress], None] | None = None,
) -> RunResult:
    config = load_run_config(workspace, config_value, validate_context=True)
    corpus_path = resolve_corpus(workspace, config.corpus)
    corpus = inspect_corpus(corpus_path, corpus_id=config.corpus, verify_lock=True)
    catalog = load_catalog(corpus_path)
    complete_dataset = load_novel(catalog, corpus.novel_id)
    selected_chapters = tuple(
        chapter
        for chapter in complete_dataset.chapters
        if config.chapters.start_inclusive <= chapter.number <= config.chapters.end_inclusive
    )
    if not selected_chapters:
        raise ValueError("configured chapter range contains no chapters")
    dataset = replace(complete_dataset, chapters=selected_chapters)
    resolved_database_url = database_url or resolve_database_url()

    started_at = _utc_now()
    run_id = f"{started_at.strftime('%Y%m%dT%H%M%S.%fZ')}-{uuid.uuid4().hex[:8]}"
    run_dir = workspace.runs / config.id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    dump_yaml_model(run_dir / "config.yaml", config)
    budget = BudgetController(config.budget.max_cost_usd, config.budget.max_wall_seconds)
    context = RunContext(
        run_id=run_id,
        run_path=run_dir,
        config=config,
        dataset=dataset,
        database_url=resolved_database_url,
        budget=budget,
        report_progress=progress_reporter or _ignore_progress,
    )
    initial_manifest: dict[str, Any] = {
        "runId": run_id,
        "configId": config.id,
        "status": "running",
        "startedAt": started_at.isoformat(),
        "finishedAt": None,
        "corpus": {"id": corpus.id, "fingerprint": corpus.fingerprint, "novelId": corpus.novel_id},
        "chapterRange": config.chapters.model_dump(mode="json"),
        "modelName": config.agent.model_name,
        "toolsets": [toolset.model_dump(mode="json") for toolset in config.agent.toolsets],
        "replicas": [],
    }
    _write_json(run_dir / "run.json", initial_manifest)
    context.report_progress(
        RunProgress(
            kind="run_started",
            run_id=run_id,
            run_path=run_dir,
            status="running",
        )
    )

    semaphore = asyncio.Semaphore(config.execution.max_parallel)

    async def execute(index: int) -> ReplicaResult:
        try:
            async with semaphore:
                context.report_progress(
                    RunProgress(
                        kind="replica_started",
                        run_id=run_id,
                        run_path=run_dir,
                        replica=index,
                        status="running",
                    )
                )
                result = await replica_executor(context, index, run_dir / "replicas" / f"replica-{index:03d}")
        except asyncio.CancelledError:
            result = ReplicaResult(
                index=index,
                status="interrupted",
                completed_chapters=(),
                usage=RunUsage(),
                failure={"type": "CancelledError", "message": "evaluation interrupted"},
            )
        except Exception as exc:
            result = ReplicaResult(
                index=index,
                status="failed",
                completed_chapters=(),
                usage=RunUsage(),
                failure=_serialize_failure(exc),
            )
        failure_message = result.failure.get("message") if result.failure is not None else None
        context.report_progress(
            RunProgress(
                kind="replica_finished",
                run_id=run_id,
                run_path=run_dir,
                replica=index,
                status=result.status,
                replica_cost_usd=result.usage.cost,
                message=str(failure_message) if failure_message is not None else None,
            )
        )
        return result

    tasks = [asyncio.create_task(execute(index)) for index in range(1, config.execution.replicas + 1)]
    interrupted = False
    try:
        results = await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        interrupted = True
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks)
    aggregate_usage = RunUsage()
    for result in results:
        aggregate_usage.incr(result.usage)
    status: RunStatus = "interrupted" if interrupted else _overall_status(results)
    finished_at = _utc_now()
    initial_manifest.update(
        {
            "status": status,
            "finishedAt": finished_at.isoformat(),
            "durationSeconds": (finished_at - started_at).total_seconds(),
            "usage": _serialize_usage(aggregate_usage),
            "replicas": [
                {
                    "replica": result.index,
                    "directory": f"replicas/replica-{result.index:03d}",
                    "status": result.status,
                    "completedChapters": list(result.completed_chapters),
                    "usage": _serialize_usage(result.usage),
                    "failure": result.failure,
                }
                for result in results
            ],
        }
    )
    _write_json(run_dir / "run.json", initial_manifest)
    context.report_progress(
        RunProgress(
            kind="run_finished",
            run_id=run_id,
            run_path=run_dir,
            status=status,
            run_cost_usd=aggregate_usage.cost,
        )
    )
    return RunResult(run_id=run_id, path=run_dir, status=status)
