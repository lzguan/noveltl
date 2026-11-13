"""Validate the stream set of a normalized stage output."""

from collections.abc import Collection, Iterable, Iterator
from uuid import UUID

from src.translations.records import TranslationRecord
from src.translations.types import ActionType, TranslationDataKey


def validate_output_records(
    records: Iterable[TranslationRecord],
    *,
    chapter_ids: Collection[UUID],
    output_type: ActionType,
) -> Iterator[TranslationRecord]:
    """Yield records whose keys form exactly the required chapter/stream set.

    Payloads are already validated by the record schemas. Retain only keys,
    not payloads, and raise ValueError for foreign chapters, unexpected streams,
    records whose type differs from their stream's, duplicates, or missing records.
    Source errors propagate unchanged.

    The caller must exhaust this iterator inside the upload context before
    publishing the artifact: completeness is checked only at exhaustion.
    """
    chapters = set(chapter_ids)
    remaining = {TranslationDataKey(chapter_id, stream) for chapter_id in chapters for stream in output_type}
    for record in records:
        key = record.key
        if key.chapter_id not in chapters:
            raise ValueError(f"Unexpected chapter in output: {key.chapter_id}")
        if key.stream not in output_type:
            raise ValueError(f"Unexpected output stream: {key.stream} for chapter {key.chapter_id}")
        if record.data_name != output_type[key.stream]:
            raise ValueError(
                f"Stream {key.stream} must hold {output_type[key.stream]} records, not {record.data_name}, "
                f"for chapter {key.chapter_id}"
            )
        if key not in remaining:
            raise ValueError(f"Duplicate output stream: {key.stream} for chapter {key.chapter_id}")
        remaining.remove(key)
        yield record

    if remaining:
        first = min(remaining, key=lambda key: (key.chapter_id, key.stream))
        raise ValueError(
            f"Missing {len(remaining)} output record(s); first: {first.stream} for chapter {first.chapter_id}"
        )
