from collections.abc import Iterator
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.translations.jsonl import encode_translation_record, iter_translation_records
from src.translations.records import ChapterRecord, MemoriesRecord


def test_round_trip_at_every_byte_boundary() -> None:
    records = [
        ChapterRecord(chapter_id=UUID(int=1), payload='第一章\n"Hello" 🌙'),
        MemoriesRecord(chapter_id=UUID(int=1), payload=[]),
    ]
    encoded = [encode_translation_record(record) for record in records]
    assert all(line.endswith(b"\n") and line.count(b"\n") == 1 for line in encoded)
    content = b"".join(encoded)
    for split in range(len(content) + 1):
        assert list(iter_translation_records([content[:split], b"", content[split:]])) == records
    assert list(iter_translation_records(bytes([byte]) for byte in content)) == records


def test_crlf_and_unterminated_final_record() -> None:
    record = ChapterRecord(chapter_id=UUID(int=1), payload="text")
    line = encode_translation_record(record).removesuffix(b"\n")
    assert list(iter_translation_records([line + b"\r", b"\n" + line])) == [record, record]
    assert list(iter_translation_records([b"", b""])) == []


@pytest.mark.parametrize(
    "content",
    [
        b"\n",
        b" \r\n",
        b'{"chapter_id":',
        b'{"chapter_id":"00000000-0000-0000-0000-000000000001","data_name":"chapter","payload":[]}',
        b'{"chapter_id":"00000000-0000-0000-0000-000000000001","data_name":"chapter","payload":"\xff"}',
    ],
)
def test_invalid_record_after_valid_record_raises(content: bytes) -> None:
    record = ChapterRecord(chapter_id=UUID(int=1), payload="valid")
    reader = iter_translation_records([encode_translation_record(record), content])
    assert next(reader) == record
    with pytest.raises(ValidationError):
        list(reader)


def test_stream_failure_propagates_without_reading_ahead() -> None:
    record = ChapterRecord(chapter_id=UUID(int=1), payload="text")

    def chunks() -> Iterator[bytes]:
        yield encode_translation_record(record)
        raise ConnectionError("download interrupted")

    reader = iter_translation_records(chunks())
    assert next(reader) == record
    with pytest.raises(ConnectionError, match="download interrupted"):
        next(reader)
