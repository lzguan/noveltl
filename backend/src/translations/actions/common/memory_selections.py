"""Resolve model-selected indices against persisted memory candidates."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import zip_longest
from uuid import UUID

from pydantic import StrictInt, TypeAdapter

from src.translations.batch_lines import BatchItemFailure, BatchItemResult
from src.translations.records import MemoriesRecord, TranslationRecord
from src.translations.types import TranslationDataKey


@dataclass(frozen=True)
class MemorySelection:
    chapter_id: UUID
    indices: list[int]


_indices_adapter = TypeAdapter(list[StrictInt])


def parse_memory_selection(result: BatchItemResult[TranslationDataKey]) -> MemorySelection:
    """Parse a JSON integer array; chapter identity comes only from the request key."""
    if isinstance(result, BatchItemFailure):
        raise ValueError(f"Memory selection failed for {result.key}: {result.error}")
    if result.key.data_name != "memories":
        raise ValueError("Memory selection requires a memories key")
    return MemorySelection(result.key.chapter_id, _indices_adapter.validate_json(result.text))


def _select(record: MemoriesRecord, selection: MemorySelection) -> MemoriesRecord:
    indices: set[int] = set()
    for index in selection.indices:
        if type(index) is not int or not 0 <= index < len(record.payload):
            raise ValueError(f"Invalid memory index {index!r} for chapter {record.chapter_id}")
        if index in indices:
            raise ValueError(f"Duplicate memory index {index} for chapter {record.chapter_id}")
        indices.add(index)
    return MemoriesRecord(
        chapter_id=record.chapter_id,
        payload=[memory for index, memory in enumerate(record.payload) if index in indices],
    )


def apply_memory_selections(
    selections: Iterable[MemorySelection],
    records: Iterable[TranslationRecord],
) -> Iterator[TranslationRecord]:
    """Match unordered streams and release each pair as soon as it is available.

    Pass non-memory records through unchanged; filter memories in original list
    order. Keep only unmatched payloads plus seen keys for duplicate detection.
    Exhaust this iterator before publishing: unmatched entries fail at the end.
    Neither input is mutated. Source exceptions propagate to the caller.
    """
    pending_selections: dict[UUID, MemorySelection] = {}
    pending_memories: dict[UUID, MemoriesRecord] = {}
    seen_selections: set[UUID] = set()
    seen_records: set[TranslationDataKey] = set()
    for selection, record in zip_longest(selections, records):
        if selection is not None:
            chapter_id = selection.chapter_id
            if chapter_id in seen_selections:
                raise ValueError(f"Duplicate memory selection for chapter {chapter_id}")
            seen_selections.add(chapter_id)
            memory = pending_memories.pop(chapter_id, None)
            if memory is None:
                pending_selections[chapter_id] = selection
            else:
                yield _select(memory, selection)
        if record is not None:
            if record.key in seen_records:
                raise ValueError(f"Duplicate input record: {record.key}")
            seen_records.add(record.key)
            if not isinstance(record, MemoriesRecord):
                yield record
                continue
            selection = pending_selections.pop(record.chapter_id, None)
            if selection is None:
                pending_memories[record.chapter_id] = record
            else:
                yield _select(record, selection)
    if pending_selections or pending_memories:
        raise ValueError(
            f"Unmatched memory inputs: {len(pending_selections)} selections without records, "
            f"{len(pending_memories)} records without selections"
        )
