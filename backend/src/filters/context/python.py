from collections.abc import Iterable, Mapping
from typing import Protocol, assert_never
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.filters.data_types import Data, DataObj, LabelRefData, TextSpanData
from src.filters.dependencies import ResolvedResourceDependency
from src.filters.functions import ResourceName
from src.novels.models import ChapterContent

type PythonResourceIds = dict[ResourceName, set[UUID]]


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
                    raise ValueError(
                        f"Dependency path {dependency.key_path!r} traverses a non-object value."
                    )
                try:
                    value = value.fields[field_name]
                except KeyError as exc:
                    raise ValueError(
                        f"Dependency path {dependency.key_path!r} references missing field "
                        f"'{field_name}'."
                    ) from exc

            if dependency.resource == "chapter_content_text":
                if not isinstance(value, TextSpanData | LabelRefData):
                    raise ValueError(
                        "Chapter content dependencies must resolve to a text span or label reference."
                    )
                resource_ids.setdefault(dependency.resource, set()).add(
                    value.value.chapter_content_id
                )
            else:
                assert_never(dependency.resource)

    return resource_ids


class PythonExecutionContext(Protocol):
    """A context for compiling and executing Python functions."""

    def get_chapter_content(self, chapter_content_id: UUID) -> str:
        """Get the text content of a chapter by its ID."""
        ...

    def load_resources(self, resource_ids: Mapping[ResourceName, set[UUID]]) -> None:
        """Bulk-load the resources needed by an execution batch."""
        ...


class PythonExecutionContextImpl:
    """A context for compiling and executing Python functions."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.chapter_content_cache: dict[UUID, str] = {}

    def get_chapter_content(self, chapter_content_id: UUID) -> str:
        """Get the text content of a chapter by its ID."""
        if chapter_content_id not in self.chapter_content_cache:
            content = self.session.execute(
                select(ChapterContent.chapter_content_text).where(
                    ChapterContent.chapter_content_id == chapter_content_id
                )
            ).scalar_one_or_none()
            if content is None:
                raise ValueError(f"Chapter content not found: {chapter_content_id}")
            self.chapter_content_cache[chapter_content_id] = content
        return self.chapter_content_cache[chapter_content_id]

    def load_resources(self, resource_ids: Mapping[ResourceName, set[UUID]]) -> None:
        """Bulk-load the resources needed by an execution batch."""
        for resource, ids in resource_ids.items():
            if resource == "chapter_content_text":
                self._load_chapter_contents(ids)
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
