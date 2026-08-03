import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, assert_never
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.filters.data_types import Data, DataObj, LabelRefData, TextSpanData
from src.filters.function_dependencies import ResolvedResourceDependency
from src.filters.functions import ResourceName
from src.labels.models import Label
from src.novels.models import ChapterContent

logger = logging.getLogger(__name__)

type PythonResourceIds = dict[ResourceName, set[UUID]]


@dataclass(frozen=True, slots=True)
class PythonLabelResource:
    word: str
    score: float
    start: int
    end: int


def collect_resource_ids(
    dependencies: tuple[ResolvedResourceDependency, ...],
    argument_sets: Iterable[tuple[Data, ...]],
) -> PythonResourceIds:
    """Collect the database resource IDs required to execute a batch."""

    resource_ids: PythonResourceIds = {}
    for arguments in argument_sets:
        for dependency in dependencies:
            try:
                value = arguments[dependency.argument_index]
            except IndexError as exc:
                raise ValueError(
                    f"Dependency references argument {dependency.argument_index}, "
                    f"but only {len(arguments)} arguments were provided."
                ) from exc

            for field_name in dependency.key_path:
                if not isinstance(value, DataObj):
                    raise ValueError(f"Dependency path {dependency.key_path!r} traverses a non-object value.")
                try:
                    value = value.fields[field_name]
                except KeyError as exc:
                    raise ValueError(
                        f"Dependency path {dependency.key_path!r} references missing field '{field_name}'."
                    ) from exc

            if dependency.resource == "chapter_content_text":
                if not isinstance(value, TextSpanData | LabelRefData):
                    raise ValueError("Chapter content dependencies must resolve to a text span or label reference.")
                resource_ids.setdefault(dependency.resource, set()).add(value.value.chapter_content_id)
            elif dependency.resource == "label":
                if not isinstance(value, LabelRefData):
                    raise ValueError("Label dependencies must resolve to a label reference.")
                resource_ids.setdefault(dependency.resource, set()).add(value.value.label_id)
            else:
                assert_never(dependency.resource)

    return resource_ids


class PythonExecutionContext(Protocol):
    """A context for compiling and executing Python functions."""

    def get_chapter_content(self, chapter_content_id: UUID) -> str:
        """Get the text content of a chapter by its ID."""
        ...

    def get_label(self, label_id: UUID) -> PythonLabelResource:
        """Get immutable label metadata by its ID."""
        ...

    def load_resources(self, resource_ids: Mapping[ResourceName, set[UUID]]) -> None:
        """Bulk-load the resources needed by an execution batch."""
        ...


class PythonExecutionContextImpl:
    """A context for compiling and executing Python functions."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.chapter_content_cache: dict[UUID, str] = {}
        self.label_cache: dict[UUID, PythonLabelResource] = {}

    def get_chapter_content(self, chapter_content_id: UUID) -> str:
        """Get the text content of a chapter by its ID."""
        if chapter_content_id not in self.chapter_content_cache:
            logger.debug(
                "Chapter content cache miss chapter_content_id=%s",
                chapter_content_id,
            )
            content = self.session.execute(
                select(ChapterContent.chapter_content_text).where(
                    ChapterContent.chapter_content_id == chapter_content_id
                )
            ).scalar_one_or_none()
            if content is None:
                raise ValueError(f"Chapter content not found: {chapter_content_id}")
            self.chapter_content_cache[chapter_content_id] = content
        return self.chapter_content_cache[chapter_content_id]

    def get_label(self, label_id: UUID) -> PythonLabelResource:
        """Get immutable label metadata by its ID."""
        if label_id not in self.label_cache:
            logger.debug("Label cache miss label_id=%s", label_id)
            row = self.session.execute(
                select(Label.label_word, Label.label_score, Label.label_start, Label.label_end).where(
                    Label.label_id == label_id
                )
            ).one_or_none()
            if row is None:
                raise ValueError(f"Label not found: {label_id}")
            self.label_cache[label_id] = PythonLabelResource(
                word=row.label_word,
                score=row.label_score,
                start=row.label_start,
                end=row.label_end,
            )
        return self.label_cache[label_id]

    def load_resources(self, resource_ids: Mapping[ResourceName, set[UUID]]) -> None:
        """Bulk-load the resources needed by an execution batch."""
        for resource, ids in resource_ids.items():
            if resource == "chapter_content_text":
                self._load_chapter_contents(ids)
            elif resource == "label":
                self._load_labels(ids)
            else:
                assert_never(resource)

    def _load_chapter_contents(self, chapter_content_ids: set[UUID]) -> None:
        if not chapter_content_ids:
            return
        missing_ids = chapter_content_ids - self.chapter_content_cache.keys()
        if not missing_ids:
            return
        rows = self.session.execute(
            select(ChapterContent.chapter_content_id, ChapterContent.chapter_content_text).where(
                ChapterContent.chapter_content_id.in_(missing_ids)
            )
        ).all()
        for chapter_content_id, chapter_content_text in rows:
            self.chapter_content_cache[chapter_content_id] = chapter_content_text

        unresolved_ids = missing_ids - self.chapter_content_cache.keys()
        if unresolved_ids:
            missing = ", ".join(sorted(str(chapter_content_id) for chapter_content_id in unresolved_ids))
            raise ValueError(f"Chapter content not found: {missing}")

    def _load_labels(self, label_ids: set[UUID]) -> None:
        if not label_ids:
            return
        missing_ids = label_ids - self.label_cache.keys()
        if not missing_ids:
            return
        rows = self.session.execute(
            select(Label.label_id, Label.label_word, Label.label_score, Label.label_start, Label.label_end).where(
                Label.label_id.in_(missing_ids)
            )
        ).all()
        for label_id, label_word, label_score, label_start, label_end in rows:
            self.label_cache[label_id] = PythonLabelResource(
                word=label_word,
                score=label_score,
                start=label_start,
                end=label_end,
            )

        unresolved_ids = missing_ids - self.label_cache.keys()
        if unresolved_ids:
            missing = ", ".join(sorted(str(label_id) for label_id in unresolved_ids))
            raise ValueError(f"Label not found: {missing}")
