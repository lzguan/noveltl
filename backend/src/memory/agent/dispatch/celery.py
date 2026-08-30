import asyncio
import json
import logging
from uuid import UUID

from src.config import log_settings
from src.database import SessionLocal
from src.memory.agent.celery_app import app
from src.memory.agent.dispatch.dispatcher import MemoryAgentDispatcher
from src.memory.agent.tasks.tasks import CompletedMemoryTask, run_all_tasks, run_task
from src.memory.exceptions import MemoryAgentEnqueueFailedException

logger = logging.getLogger(__name__)
AGENT_RESULT_LOG_MARKER = "MEMORY_AGENT_RESULT "
# Append-only JSONL sink capturing each completed task's full LLM output
# (messages) alongside its job id, usage, and identifiers. One JSON object per
# line; both the directory and filename are configurable.
AGENT_RESULT_JSONL_PATH = log_settings.MEMORY_AGENT_LOG_DIR / log_settings.MEMORY_AGENT_LOG_FILENAME


def _build_agent_result_payload(completed_task: CompletedMemoryTask) -> dict:
    result = completed_task.result
    usage = result.usage
    return {
        "event": "memoryAgent.result",
        "memoryJobId": str(completed_task.memory_job_id),
        "memoryGroupId": str(completed_task.memory_group_id),
        "chapterId": str(completed_task.chapter_id),
        "chapterContentId": str(completed_task.chapter_content_id),
        "chapterNum": completed_task.chapter_num,
        "runId": result.run_id,
        "timestamp": result.timestamp.isoformat(),
        "output": result.output,
        "usage": {
            "requests": usage.requests,
            "toolCalls": usage.tool_calls,
            "inputTokens": usage.input_tokens,
            "outputTokens": usage.output_tokens,
            "cacheWriteTokens": usage.cache_write_tokens,
            "cacheReadTokens": usage.cache_read_tokens,
            "totalTokens": usage.total_tokens,
            "costUsd": str(usage.cost) if usage.cost is not None else None,
            "details": usage.details,
        },
        "messages": json.loads(result.all_messages_json()),
    }


def _append_agent_result_jsonl(payload: dict) -> None:
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    try:
        AGENT_RESULT_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AGENT_RESULT_JSONL_PATH.open("a", encoding="utf-8") as jsonl_file:
            jsonl_file.write(line + "\n")
    except OSError:
        # Never let a logging-sink failure interrupt the job.
        logger.exception(
            "Failed to append memory-agent result to %s job_id=%s",
            AGENT_RESULT_JSONL_PATH,
            payload.get("memoryJobId"),
        )


def _log_agent_result(completed_task: CompletedMemoryTask) -> None:
    payload = _build_agent_result_payload(completed_task)
    _append_agent_result_jsonl(payload)
    logger.info(
        "%s%s",
        AGENT_RESULT_LOG_MARKER,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )


@app.task
def run_memory_job(memory_job_id: str) -> None:
    """Celery entry point for processing every pending task in a memory job."""

    async def consume_job() -> None:
        async for completed_task in run_all_tasks(SessionLocal, UUID(memory_job_id)):
            _log_agent_result(completed_task)

    asyncio.run(consume_job())


@app.task
def run_memory_task(memory_job_id: str, chapter_id: str) -> None:
    """Celery entry point for processing one pending chapter task."""
    completed_task = asyncio.run(run_task(SessionLocal, UUID(memory_job_id), UUID(chapter_id)))
    if completed_task is not None:
        _log_agent_result(completed_task)


class CeleryMemoryAgentDispatcher(MemoryAgentDispatcher):
    """Publish memory-agent work to Celery using JSON-safe identifiers."""

    def enqueue_job(self, memory_job_id: UUID) -> None:
        try:
            logger.info("Enqueuing memory-agent job job_id=%s", memory_job_id)
            run_memory_job.apply_async((str(memory_job_id),), task_id=str(memory_job_id))
        except Exception as exc:
            logger.exception("Memory-agent job enqueue failed job_id=%s", memory_job_id)
            raise MemoryAgentEnqueueFailedException(f"Celery enqueue failed: {exc}") from exc

    def enqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        try:
            logger.info("Enqueuing memory-agent task job_id=%s chapter_id=%s", memory_job_id, chapter_id)
            run_memory_task.apply_async(
                (str(memory_job_id), str(chapter_id)),
                task_id=f"{memory_job_id}:{chapter_id}",
            )
        except Exception as exc:
            logger.exception("Memory-agent task enqueue failed job_id=%s chapter_id=%s", memory_job_id, chapter_id)
            raise MemoryAgentEnqueueFailedException(f"Celery enqueue failed: {exc}") from exc

    async def aenqueue_job(self, memory_job_id: UUID) -> None:
        await asyncio.to_thread(self.enqueue_job, memory_job_id)

    async def aenqueue_task(self, memory_job_id: UUID, chapter_id: UUID) -> None:
        await asyncio.to_thread(self.enqueue_task, memory_job_id, chapter_id)
