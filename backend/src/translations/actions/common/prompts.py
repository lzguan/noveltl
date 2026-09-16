"""Shared prompt formatting for translation actions."""

import json
from typing import Literal

from src.memory.schemas import Memory

type MemoryPromptField = Literal["content", "type", "mark", "plugin", "start_chapter", "end_chapter", "review_status"]


def format_memories(
    memories: list[Memory],
    *,
    fields: tuple[MemoryPromptField, ...] = ("content", "type", "mark"),
) -> str:
    """Format prompt context with zero-based indices into the original list.

    Preserve order and include every entry so returned indices can be resolved
    against the saved candidates. Indices are always included; metadata fields
    are opt-in. Database identifiers stay out of the prompt.
    """
    records: list[dict[str, object]] = []
    for index, memory in enumerate(memories):
        available: dict[MemoryPromptField, object] = {
            "plugin": memory.plugin_name,
            "type": memory.memory_type,
            "mark": memory.mark,
            "content": memory.memory_content,
            "start_chapter": memory.memory_start_num,
            "end_chapter": memory.memory_end_num,
            "review_status": memory.memory_review_status,
        }
        records.append({"index": index, **{field: available[field] for field in fields}})
    return json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":"),
    )
