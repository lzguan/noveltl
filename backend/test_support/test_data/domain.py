from dataclasses import dataclass, field
from pathlib import Path

from .formats.v1.documents import AutoLabel, ModelConfigDocument, Provenance, RelationBundleDocument


@dataclass(frozen=True)
class AutoLabelArtifact:
    id: str
    producer_name: str
    config_id: str
    labels: tuple[AutoLabel, ...]
    errors: tuple[dict[str, object], ...]
    path: Path


@dataclass(frozen=True)
class ContentVersionDataset:
    id: str
    number: int
    text: str
    artifacts: tuple[AutoLabelArtifact, ...]
    path: Path


@dataclass(frozen=True)
class ChapterDataset:
    id: str
    number: int
    title: str
    is_public: bool
    versions: tuple[ContentVersionDataset, ...]
    path: Path


@dataclass(frozen=True)
class NovelDataset:
    id: str
    title: str
    description: str | None
    author: str | None
    language_code: str
    novel_type: str
    visibility: str
    provenance: Provenance
    chapters: tuple[ChapterDataset, ...]
    path: Path


@dataclass
class Catalog:
    root: Path
    schema_version: int
    configs: dict[str, Path]
    novels: dict[str, Path]
    relations: dict[str, Path]
    document_paths: set[Path] = field(default_factory=set)
    content_paths: set[Path] = field(default_factory=set)
    configs_cache: dict[str, ModelConfigDocument] = field(default_factory=dict)
    novels_cache: dict[str, NovelDataset] = field(default_factory=dict)
    relations_cache: dict[str, RelationBundleDocument] = field(default_factory=dict)
    registered_ids: dict[str, Path] = field(default_factory=dict)
