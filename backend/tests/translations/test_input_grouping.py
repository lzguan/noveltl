from collections.abc import Iterator
from uuid import UUID

import pytest

from src.translations.actions.common.inputs import group_by_chapter
from src.translations.records import ChapterRecord, MemoriesRecord, TranslationRecord

A, B = UUID(int=1), UUID(int=2)


def test_groups_by_stream_name_with_interleaved_chapters_and_shared_record_types() -> None:
    draft_a = ChapterRecord(chapter_id=A, stream="draft", payload="Draft A")
    reference_a = ChapterRecord(chapter_id=A, stream="reference", payload="Reference A")
    draft_b = ChapterRecord(chapter_id=B, stream="draft", payload="Draft B")
    reference_b = ChapterRecord(chapter_id=B, stream="reference", payload="Reference B")
    empty_a = MemoriesRecord(chapter_id=A, stream="context", payload=[])
    empty_b = MemoriesRecord(chapter_id=B, stream="context", payload=[])
    records = [reference_a, draft_b, empty_b, reference_b, empty_a, draft_a]
    output = list(group_by_chapter(records, {"draft", "reference", "context"}))
    assert output == [
        {"draft": draft_b, "reference": reference_b, "context": empty_b},
        {"draft": draft_a, "reference": reference_a, "context": empty_a},
    ]
    assert output[0]["draft"] is draft_b
    assert output[1]["reference"] is reference_a


def test_groups_stream_incrementally_and_propagates_source_failure() -> None:
    chapter = ChapterRecord(chapter_id=A, stream="draft", payload="A")

    def records() -> Iterator[TranslationRecord]:
        yield chapter
        raise ConnectionError("download interrupted")

    output = group_by_chapter(records(), {"draft"})
    assert next(output) == {"draft": chapter}
    with pytest.raises(ConnectionError, match="download interrupted"):
        next(output)


def test_rejects_an_incomplete_group_after_yielding_complete_chapters() -> None:
    records = [
        ChapterRecord(chapter_id=A, stream="draft", payload="A"),
        ChapterRecord(chapter_id=B, stream="draft", payload="B"),
        ChapterRecord(chapter_id=B, stream="reference", payload="Reference B"),
    ]
    output = group_by_chapter(records, {"draft", "reference"})
    assert next(output) == {"draft": records[1], "reference": records[2]}
    with pytest.raises(ValueError, match=f"Missing input streams for chapter {A}: reference"):
        next(output)


def test_empty_input_has_no_groups() -> None:
    assert list(group_by_chapter([], {"draft", "reference"})) == []
