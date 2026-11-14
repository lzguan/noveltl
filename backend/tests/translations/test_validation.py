from collections.abc import Iterator
from uuid import UUID

import pytest

from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.types import ActionType
from src.translations.validation import validate_output_records

CHAPTER_A = UUID(int=1)
CHAPTER_B = UUID(int=2)
CHAPTER: ActionType = {"chapter": "chapter"}
BOTH: ActionType = {"chapter": "chapter", "memories": "memories"}


def chapter(chapter_id: UUID, payload: str) -> ChapterRecord:
    return ChapterRecord(chapter_id=chapter_id, stream="chapter", payload=payload)


def memories(chapter_id: UUID, stream: str = "memories") -> MemoriesRecord:
    return MemoriesRecord(chapter_id=chapter_id, stream=stream, payload=[])


def test_complete_output_preserves_order_and_records() -> None:
    records = [memories(CHAPTER_B), chapter(CHAPTER_A, "A"), chapter(CHAPTER_B, "B"), memories(CHAPTER_A)]
    output = list(validate_output_records(iter(records), chapter_ids=[CHAPTER_A, CHAPTER_B], output_type=BOTH))
    assert output == records
    assert all(actual is original for actual, original in zip(output, records, strict=True))


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        (chapter(CHAPTER_B, "foreign"), "Unexpected chapter"),
        (memories(CHAPTER_A), "Unexpected output stream"),
        (memories(CHAPTER_A, stream="chapter"), "Stream chapter must hold chapter records, not memories"),
        (chapter(CHAPTER_A, "duplicate with different content"), "Duplicate output stream"),
    ],
)
def test_invalid_record_is_rejected_before_yield(invalid: TranslationRecord, message: str) -> None:
    valid = chapter(CHAPTER_A, "A")
    output = validate_output_records([valid, invalid], chapter_ids=[CHAPTER_A], output_type=CHAPTER)
    assert next(output) == valid
    with pytest.raises(ValueError, match=message):
        next(output)


def test_stream_names_are_checked_against_their_declared_type() -> None:
    renamed: ActionType = {"draft": "chapter"}
    record = ChapterRecord(chapter_id=CHAPTER_A, stream="draft", payload="A")
    assert list(validate_output_records([record], chapter_ids=[CHAPTER_A], output_type=renamed)) == [record]
    with pytest.raises(ValueError, match="Unexpected output stream: chapter"):
        list(validate_output_records([chapter(CHAPTER_A, "A")], chapter_ids=[CHAPTER_A], output_type=renamed))


def test_missing_record_is_detected_at_exhaustion() -> None:
    record = chapter(CHAPTER_A, "A")
    output = validate_output_records([record], chapter_ids=[CHAPTER_A, CHAPTER_B], output_type=BOTH)
    assert next(output) == record
    with pytest.raises(ValueError, match=f"Missing 3 output record.*memories for chapter {CHAPTER_A}"):
        next(output)


def test_empty_output_requires_empty_expected_set() -> None:
    assert list(validate_output_records([], chapter_ids=[], output_type=CHAPTER)) == []
    assert list(validate_output_records([], chapter_ids=[CHAPTER_A], output_type={})) == []
    with pytest.raises(ValueError, match="Missing 1 output record"):
        list(validate_output_records([], chapter_ids=[CHAPTER_A], output_type=CHAPTER))


def test_source_failure_propagates_after_last_required_record() -> None:
    record = chapter(CHAPTER_A, "A")

    def source() -> Iterator[TranslationRecord]:
        yield record
        raise ConnectionError("download interrupted")

    output = validate_output_records(source(), chapter_ids=[CHAPTER_A], output_type=CHAPTER)
    assert next(output) == record
    with pytest.raises(ConnectionError, match="download interrupted"):
        next(output)
