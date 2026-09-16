"""Worker-side task registration; imports the agent implementation and its SDK."""

import asyncio
import json
import logging
from uuid import UUID

from src.config import log_settings
from src.database import SessionLocal
from src.memory.agent.capabilities.continuity import ContinuitySummaryOutput
from src.memory.agent.celery_app import app
from src.memory.agent.task_names import RUN_MEMORY_JOB, RUN_MEMORY_TASK
from src.memory.agent.tasks.tasks import CompletedMemoryTask, run_all_tasks, run_task

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
        "output": (
            result.output.model_dump(mode="json")
            if isinstance(result.output, ContinuitySummaryOutput)
            else result.output
        ),
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


@app.task(name=RUN_MEMORY_JOB)
def run_memory_job(memory_job_id: str) -> None:
    """Celery entry point for processing every pending task in a memory job."""

    async def consume_job() -> None:
        async for completed_task in run_all_tasks(SessionLocal, UUID(memory_job_id)):
            _log_agent_result(completed_task)

    asyncio.run(consume_job())


@app.task(name=RUN_MEMORY_TASK)
def run_memory_task(memory_job_id: str, chapter_id: str) -> None:
    """Celery entry point for processing one pending chapter task."""
    completed_task = asyncio.run(run_task(SessionLocal, UUID(memory_job_id), UUID(chapter_id)))
    if completed_task is not None:
        _log_agent_result(completed_task)
