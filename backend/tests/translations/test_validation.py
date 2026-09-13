from collections.abc import Iterator
from uuid import UUID

import pytest

from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord
from src.translations.validation import validate_output_records

CHAPTER_A = UUID(int=1)
CHAPTER_B = UUID(int=2)


def test_complete_output_preserves_order_and_records() -> None:
    records = [
        MemoriesRecord(chapter_id=CHAPTER_B, payload=[]),
        ChapterRecord(chapter_id=CHAPTER_A, payload="A"),
        ChapterRecord(chapter_id=CHAPTER_B, payload="B"),
        MemoriesRecord(chapter_id=CHAPTER_A, payload=[]),
    ]
    output = list(
        validate_output_records(
            iter(records), chapter_ids=[CHAPTER_A, CHAPTER_B], output_types=frozenset({"chapter", "memories"})
        )
    )
    assert output == records
    assert all(actual is original for actual, original in zip(output, records, strict=True))


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        (ChapterRecord(chapter_id=CHAPTER_B, payload="foreign"), "Unexpected chapter"),
        (MemoriesRecord(chapter_id=CHAPTER_A, payload=[]), "Unexpected output component"),
        (ChapterRecord(chapter_id=CHAPTER_A, payload="duplicate with different content"), "Duplicate output component"),
    ],
)
def test_invalid_key_is_rejected_before_yield(invalid: TranslationRecord, message: str) -> None:
    valid = ChapterRecord(chapter_id=CHAPTER_A, payload="A")
    output = validate_output_records([valid, invalid], chapter_ids=[CHAPTER_A], output_types=frozenset({"chapter"}))
    assert next(output) == valid
    with pytest.raises(ValueError, match=message):
        next(output)


def test_missing_component_is_detected_at_exhaustion() -> None:
    record = ChapterRecord(chapter_id=CHAPTER_A, payload="A")
    output = validate_output_records(
        [record], chapter_ids=[CHAPTER_A, CHAPTER_B], output_types=frozenset({"chapter", "memories"})
    )
    assert next(output) == record
    with pytest.raises(ValueError, match=f"Missing 3 output component.*memories for chapter {CHAPTER_A}"):
        next(output)


def test_empty_output_requires_empty_expected_set() -> None:
    assert list(validate_output_records([], chapter_ids=[], output_types=frozenset({"chapter"}))) == []
    with pytest.raises(ValueError, match="Missing 1 output component"):
        list(validate_output_records([], chapter_ids=[CHAPTER_A], output_types=frozenset({"chapter"})))


def test_source_failure_propagates_after_last_required_record() -> None:
    record = ChapterRecord(chapter_id=CHAPTER_A, payload="A")

    def source() -> Iterator[TranslationRecord]:
        yield record
        raise ConnectionError("download interrupted")

    output = validate_output_records(source(), chapter_ids=[CHAPTER_A], output_types=frozenset({"chapter"}))
    assert next(output) == record
    with pytest.raises(ConnectionError, match="download interrupted"):
        next(output)
