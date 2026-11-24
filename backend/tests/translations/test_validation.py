from collections.abc import AsyncIterator
from uuid import UUID

import pytest

from src.lib.aiter import as_async_iter
from src.translations.records import ChapterRecord, ConventionsRecord, MemoriesRecord, TermsRecord, TranslationRecord
from src.translations.types import ActionType
from src.translations.validation import validate_output_records
from test_support.aiter import alist

CHAPTER_A = UUID(int=1)
CHAPTER_B = UUID(int=2)
CHAPTER: ActionType = {"chapter": "chapter"}
BOTH: ActionType = {"chapter": "chapter", "memories": "memories"}


def chapter(chapter_id: UUID, payload: str) -> ChapterRecord:
    return ChapterRecord(chapter_id=chapter_id, stream="chapter", payload=payload)


def memories(chapter_id: UUID, stream: str = "memories") -> MemoriesRecord:
    return MemoriesRecord(chapter_id=chapter_id, stream=stream, payload=[])


async def test_complete_output_preserves_order_and_records() -> None:
    records = [memories(CHAPTER_B), chapter(CHAPTER_A, "A"), chapter(CHAPTER_B, "B"), memories(CHAPTER_A)]
    output = await alist(
        validate_output_records(as_async_iter(records), chapter_ids=[CHAPTER_A, CHAPTER_B], output_type=BOTH)
    )
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
async def test_invalid_record_is_rejected_before_yield(invalid: TranslationRecord, message: str) -> None:
    valid = chapter(CHAPTER_A, "A")
    output = validate_output_records(as_async_iter([valid, invalid]), chapter_ids=[CHAPTER_A], output_type=CHAPTER)
    assert await anext(output) == valid
    with pytest.raises(ValueError, match=message):
        await anext(output)


async def test_stream_names_are_checked_against_their_declared_type() -> None:
    renamed: ActionType = {"draft": "chapter"}
    record = ChapterRecord(chapter_id=CHAPTER_A, stream="draft", payload="A")
    assert await alist(
        validate_output_records(as_async_iter([record]), chapter_ids=[CHAPTER_A], output_type=renamed)
    ) == [record]
    with pytest.raises(ValueError, match="Unexpected output stream: chapter"):
        await alist(
            validate_output_records(
                as_async_iter([chapter(CHAPTER_A, "A")]), chapter_ids=[CHAPTER_A], output_type=renamed
            )
        )


async def test_terms_and_conventions_are_complete_typed_streams() -> None:
    expected: ActionType = {"terms": "terms", "conventions": "conventions"}
    records = [
        TermsRecord(chapter_id=CHAPTER_A, stream="terms", payload={"白玫": "White Rose"}),
        ConventionsRecord(chapter_id=CHAPTER_A, stream="conventions", payload=[]),
    ]
    assert (
        await alist(validate_output_records(as_async_iter(records), chapter_ids=[CHAPTER_A], output_type=expected))
        == records
    )
    with pytest.raises(ValueError, match="Missing 1 output record.*conventions"):
        await alist(validate_output_records(as_async_iter(records[:1]), chapter_ids=[CHAPTER_A], output_type=expected))
    with pytest.raises(ValueError, match="Stream terms must hold conventions records, not terms"):
        await alist(
            validate_output_records(
                as_async_iter(records[:1]), chapter_ids=[CHAPTER_A], output_type={"terms": "conventions"}
            )
        )


async def test_missing_record_is_detected_at_exhaustion() -> None:
    record = chapter(CHAPTER_A, "A")
    output = validate_output_records(as_async_iter([record]), chapter_ids=[CHAPTER_A, CHAPTER_B], output_type=BOTH)
    assert await anext(output) == record
    with pytest.raises(ValueError, match=f"Missing 3 output record.*memories for chapter {CHAPTER_A}"):
        await anext(output)


async def test_empty_output_requires_empty_expected_set() -> None:
    assert await alist(validate_output_records(as_async_iter([]), chapter_ids=[], output_type=CHAPTER)) == []
    assert await alist(validate_output_records(as_async_iter([]), chapter_ids=[CHAPTER_A], output_type={})) == []
    with pytest.raises(ValueError, match="Missing 1 output record"):
        await alist(validate_output_records(as_async_iter([]), chapter_ids=[CHAPTER_A], output_type=CHAPTER))


async def test_source_failure_propagates_after_last_required_record() -> None:
    record = chapter(CHAPTER_A, "A")

    async def source() -> AsyncIterator[TranslationRecord]:
        yield record
        raise ConnectionError("download interrupted")

    output = validate_output_records(source(), chapter_ids=[CHAPTER_A], output_type=CHAPTER)
    assert await anext(output) == record
    with pytest.raises(ConnectionError, match="download interrupted"):
        await anext(output)
