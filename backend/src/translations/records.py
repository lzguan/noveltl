"""Canonical records for initial inputs and normalized stage outputs."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, TypeAdapter

from src.memory.schemas import Memory
from src.schemas import Model
from src.translations.types import TranslationDataKey


class ChapterRecord(Model):
    """One complete source or translated chapter text."""

    model_config = ConfigDict(alias_generator=None, extra="forbid")

    chapter_id: UUID
    data_name: Literal["chapter"] = "chapter"
    payload: str

    @property
    def key(self) -> TranslationDataKey:
        return TranslationDataKey(self.chapter_id, self.data_name)


class MemoriesRecord(Model):
    """The complete selected memory collection for one chapter, possibly empty."""

    model_config = ConfigDict(alias_generator=None, extra="forbid")

    chapter_id: UUID
    data_name: Literal["memories"] = "memories"
    payload: list[Memory]

    @property
    def key(self) -> TranslationDataKey:
        return TranslationDataKey(self.chapter_id, self.data_name)


type TranslationRecord = Annotated[ChapterRecord | MemoriesRecord, Field(discriminator="data_name")]

translation_record_adapter = TypeAdapter(TranslationRecord)
