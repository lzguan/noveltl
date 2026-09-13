"""Streaming serialization of canonical translation artifacts."""

from collections.abc import Iterable, Iterator

from src.translations.records import TranslationRecord, translation_record_adapter


def encode_translation_record(record: TranslationRecord) -> bytes:
    """Encode one canonical record as UTF-8 JSON followed by a newline."""
    return record.model_dump_json(by_alias=False).encode("utf-8") + b"\n"


def iter_translation_records(chunks: Iterable[bytes]) -> Iterator[TranslationRecord]:
    """Read records from arbitrary byte chunks, buffering one unfinished line.

    Accept CRLF and a final record without a newline. Empty streams yield no
    records; blank lines and invalid records raise Pydantic ValidationError.
    Upstream stream errors propagate to the caller.
    """
    pending = bytearray()
    for chunk in chunks:
        start = 0
        while (end := chunk.find(b"\n", start)) != -1:
            pending.extend(chunk[start:end])
            yield translation_record_adapter.validate_json(pending)
            pending.clear()
            start = end + 1
        pending.extend(chunk[start:])
    if pending:
        yield translation_record_adapter.validate_json(pending)
