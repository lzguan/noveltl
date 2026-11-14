"""Canonical records for initial inputs and normalized stage outputs."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, TypeAdapter

from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.schemas import Memory
from src.schemas import Model
from src.translations.types import TranslationDataKey


class ChapterRecord(Model):
    """One complete source or translated chapter text."""

    model_config = ConfigDict(alias_generator=None, extra="forbid")

    chapter_id: UUID
    stream: str
    data_name: Literal["chapter"] = "chapter"
    payload: str

    @property
    def key(self) -> TranslationDataKey:
        return TranslationDataKey(self.chapter_id, self.stream)


class MemoriesRecord(Model):
    """The complete selected memory collection for one chapter, possibly empty."""

    model_config = ConfigDict(alias_generator=None, extra="forbid")

    chapter_id: UUID
    stream: str
    data_name: Literal["memories"] = "memories"
    payload: list[Memory]

    @property
    def key(self) -> TranslationDataKey:
        return TranslationDataKey(self.chapter_id, self.stream)


class TermsRecord(Model):
    model_config = ConfigDict(alias_generator=None, extra="forbid")

    chapter_id: UUID
    stream: str
    data_name: Literal["terms"] = "terms"
    payload: dict[str, str]

    @property
    def key(self) -> TranslationDataKey:
        return TranslationDataKey(self.chapter_id, self.stream)


class ConventionContent(Model):
    model_config = ConfigDict(alias_generator=None, extra="forbid")

    category: ConventionCategory
    title: str
    rule: str
    rationale: str | None


class ConventionsRecord(Model):
    model_config = ConfigDict(alias_generator=None, extra="forbid")

    chapter_id: UUID
    stream: str
    data_name: Literal["conventions"] = "conventions"
    payload: list[ConventionContent]

    @property
    def key(self) -> TranslationDataKey:
        return TranslationDataKey(self.chapter_id, self.stream)


type TranslationRecord = Annotated[
    ChapterRecord | MemoriesRecord | TermsRecord | ConventionsRecord, Field(discriminator="data_name")
]

translation_record_adapter = TypeAdapter(TranslationRecord)
