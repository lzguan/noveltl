"""Validate the component set of a normalized stage output."""

from collections.abc import Collection, Iterable, Iterator
from uuid import UUID

from src.translations.records import TranslationRecord
from src.translations.types import DataT, TranslationDataKey


def validate_output_records(
    records: Iterable[TranslationRecord],
    *,
    chapter_ids: Collection[UUID],
    output_types: DataT,
) -> Iterator[TranslationRecord]:
    """Yield records whose keys form exactly the required chapter/component set.

    Payloads are already validated by the record schemas. Retain only keys,
    not payloads, and raise ValueError for foreign chapters, unexpected types,
    duplicates, or missing components. Source errors propagate unchanged.

    The caller must exhaust this iterator inside the upload context before
    publishing the artifact: completeness is checked only at exhaustion.
    """
    chapters = set(chapter_ids)
    remaining = {TranslationDataKey(chapter_id, data_name) for chapter_id in chapters for data_name in output_types}
    for record in records:
        key = record.key
        if key.chapter_id not in chapters:
            raise ValueError(f"Unexpected chapter in output: {key.chapter_id}")
        if key.data_name not in output_types:
            raise ValueError(f"Unexpected output component: {key.data_name} for chapter {key.chapter_id}")
        if key not in remaining:
            raise ValueError(f"Duplicate output component: {key.data_name} for chapter {key.chapter_id}")
        remaining.remove(key)
        yield record

    if remaining:
        first = min(remaining, key=lambda key: (key.chapter_id, key.data_name))
        raise ValueError(
            f"Missing {len(remaining)} output component(s); first: {first.data_name} for chapter {first.chapter_id}"
        )
