from collections.abc import Iterator
from uuid import UUID

import pytest

from src.memory.schemas import Memory
from src.translations.actions.common.memory_selections import (
    MemorySelection,
    apply_memory_selections,
    parse_memory_selection,
)
from src.translations.batch_lines import BatchItemFailure, BatchItemSuccess
from src.translations.records import ChapterRecord, MemoriesRecord
from src.translations.types import TranslationDataKey

A, B = UUID(int=1), UUID(int=2)


def candidates(chapter_id: UUID) -> MemoriesRecord:
    return MemoriesRecord(
        chapter_id=chapter_id,
        payload=[
            Memory.model_validate(
                {
                    "memory_id": UUID(int=10 + i),
                    "memory_type": "fact",
                    "mark": None,
                    "memory_content": f"Memory {i}",
                    "memory_start_num": 0,
                    "memory_end_num": None,
                    "memory_review_status": "pending",
                    "supersedes_memory_id": None,
                    "creator_type": "user",
                    "plugin_name": "continuity",
                }
            )
            for i in range(3)
        ],
    )


def test_parse_uses_request_identity_and_accepts_empty_selection() -> None:
    key = TranslationDataKey(A, "memories")
    assert parse_memory_selection(BatchItemSuccess(key, "[2, 0]")) == MemorySelection(A, [2, 0])
    assert parse_memory_selection(BatchItemSuccess(key, "[]")) == MemorySelection(A, [])


@pytest.mark.parametrize("text", ["[true]", '["0"]', "[1.0]", "{}", "null", "```json\n[0]\n```"])
def test_parse_rejects_non_integer_arrays(text: str) -> None:
    with pytest.raises(ValueError):
        parse_memory_selection(BatchItemSuccess(TranslationDataKey(A, "memories"), text))


def test_parse_rejects_wrong_component_and_provider_failure() -> None:
    with pytest.raises(ValueError, match="memories key"):
        parse_memory_selection(BatchItemSuccess(TranslationDataKey(A, "chapter"), "[]"))
    with pytest.raises(ValueError, match="provider failed"):
        parse_memory_selection(BatchItemFailure(TranslationDataKey(A, "memories"), "provider failed"))


def test_match_unordered_streams_passes_chapters_and_preserves_candidate_order() -> None:
    # Pruning finalization needs selections to resolve against exactly the saved
    # snapshots, irrespective of provider order, without retaining matched data.
    a, b = candidates(A), candidates(B)
    chapter = ChapterRecord(chapter_id=A, payload="Original chapter")
    output = list(
        apply_memory_selections(
            iter([MemorySelection(B, []), MemorySelection(A, [2, 0])]),
            iter([a, chapter, b]),
        )
    )
    assert output == [
        MemoriesRecord(chapter_id=A, payload=[a.payload[0], a.payload[2]]),
        chapter,
        MemoriesRecord(chapter_id=B, payload=[]),
    ]
    assert len(a.payload) == 3 and len(b.payload) == 3


def test_yields_pair_before_consuming_rest_and_propagates_source_failure() -> None:
    def selections() -> Iterator[MemorySelection]:
        yield MemorySelection(A, [])
        raise ConnectionError("interrupted")

    output = apply_memory_selections(selections(), [candidates(A)])
    assert next(output) == MemoriesRecord(chapter_id=A, payload=[])
    with pytest.raises(ConnectionError, match="interrupted"):
        next(output)


@pytest.mark.parametrize("indices", [[-1], [3], [0, 0]])
def test_rejects_invalid_or_duplicate_indices(indices: list[int]) -> None:
    with pytest.raises(ValueError, match="memory index"):
        list(apply_memory_selections([MemorySelection(A, indices)], [candidates(A)]))


@pytest.mark.parametrize("duplicate_selection", [True, False])
def test_detects_duplicates_after_pair_was_removed(duplicate_selection: bool) -> None:
    selections = [MemorySelection(A, [])]
    records = [candidates(A)]
    if duplicate_selection:
        selections += selections
    else:
        records += records
    output = apply_memory_selections(selections, records)
    assert next(output) == MemoriesRecord(chapter_id=A, payload=[])
    with pytest.raises(ValueError, match="Duplicate"):
        list(output)


@pytest.mark.parametrize("selection_only", [True, False])
def test_rejects_unmatched_inputs_at_exhaustion(selection_only: bool) -> None:
    with pytest.raises(ValueError, match="Unmatched"):
        list(
            apply_memory_selections(
                [MemorySelection(A, [])] if selection_only else [],
                [] if selection_only else [candidates(A)],
            )
        )
