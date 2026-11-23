"""Result logging shared by every memory-agent worker implementation."""

import json
import logging

from pydantic import BaseModel

from src.config import log_settings
from src.memory.agent.tasks.tasks import CompletedMemoryTask

logger = logging.getLogger(__name__)
AGENT_RESULT_LOG_MARKER = "MEMORY_AGENT_RESULT "
# Append-only JSONL sink capturing each completed task's full LLM output
# (messages) alongside its job id, usage, and identifiers. One JSON object per
# line; both the directory and filename are configurable.
AGENT_RESULT_JSONL_PATH = log_settings.MEMORY_AGENT_LOG_DIR / log_settings.MEMORY_AGENT_LOG_FILENAME


def _build_agent_result_payload(completed_task: CompletedMemoryTask) -> dict:
    result = completed_task.result
    if result is None:
        return {
            "event": "memoryAgent.skipped",
            "memoryJobId": str(completed_task.memory_job_id),
            "chapterId": str(completed_task.chapter_id),
            "stageNum": completed_task.stage_num,
            "stageName": completed_task.stage_name,
            "reason": "No terms need translation",
        }
    usage = result.usage
    return {
        "event": "memoryAgent.result",
        "memoryJobId": str(completed_task.memory_job_id),
        "memoryGroupId": str(completed_task.memory_group_id),
        "chapterId": str(completed_task.chapter_id),
        "chapterContentId": str(completed_task.chapter_content_id),
        "chapterNum": completed_task.chapter_num,
        "stageNum": completed_task.stage_num,
        "stageName": completed_task.stage_name,
        "runId": result.run_id,
        "timestamp": result.timestamp.isoformat(),
        "output": (result.output.model_dump(mode="json") if isinstance(result.output, BaseModel) else result.output),
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


def log_agent_result(completed_task: CompletedMemoryTask) -> None:
    payload = _build_agent_result_payload(completed_task)
    _append_agent_result_jsonl(payload)
    logger.info(
        "%s%s",
        AGENT_RESULT_LOG_MARKER,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
