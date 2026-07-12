import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .domain import AutoLabelArtifact, Catalog, ChapterDataset, ContentVersionDataset, NovelDataset
from .errors import DuplicateIdError, ReferenceError, TestDataError, UnsupportedDocumentError
from .formats.v1.documents import (
    DOCUMENT_MODELS,
    AutoLabelsDocument,
    CatalogDocument,
    ChapterManifestDocument,
    ContentVersionManifestDocument,
    Document,
    ModelConfigDocument,
    NovelManifestDocument,
    Reference,
    RelationBundleDocument,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReferenceError("Could not read JSON document", path) from exc
    if not isinstance(data, dict):
        raise ReferenceError("JSON document must be an object", path)
    return data


def _parse_document[DocumentT: Document](path: Path, expected: type[DocumentT]) -> DocumentT:
    data = _read_json(path)
    kind = data.get("kind")
    schema_version = data.get("schemaVersion")
    if not isinstance(kind, str) or not isinstance(schema_version, int):
        raise UnsupportedDocumentError(kind, schema_version)
    key = (kind, schema_version)
    model = DOCUMENT_MODELS.get(key)
    if model is None:
        raise UnsupportedDocumentError(*key)
    if model is not expected:
        raise ReferenceError(f"Expected {expected.__name__}, found {model.__name__}", path)
    try:
        return expected.model_validate(data)
    except ValidationError as exc:
        raise ReferenceError(f"Invalid {expected.__name__}: {exc}", path) from exc


def _resolve(base: Path, relative: str, root: Path) -> Path:
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ReferenceError("Reference escapes dataset root", candidate) from exc
    if not candidate.is_file():
        raise ReferenceError("Referenced file does not exist", candidate)
    return candidate


def _register(catalog: Catalog, logical_id: str, path: Path) -> None:
    existing = catalog.registered_ids.get(logical_id)
    if existing is not None and existing != path:
        raise DuplicateIdError(logical_id)
    catalog.registered_ids[logical_id] = path


def _index_references(root: Path, refs: list[Reference], category: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for ref in refs:
        if ref.id in result:
            raise DuplicateIdError(ref.id)
        result[ref.id] = _resolve(root, ref.path, root)
    return result


def load_catalog(root: Path | str) -> Catalog:
    dataset_root = Path(root).resolve()
    document = _parse_document(dataset_root / "catalog.json", CatalogDocument)
    catalog = Catalog(
        root=dataset_root,
        schema_version=document.schema_version,
        configs=_index_references(dataset_root, document.configs, "configs"),
        novels=_index_references(dataset_root, document.novels, "novels"),
        relations=_index_references(dataset_root, document.relations, "relations"),
    )
    catalog.document_paths.add(dataset_root / "catalog.json")
    for mapping in (catalog.configs, catalog.novels, catalog.relations):
        for logical_id, path in mapping.items():
            _register(catalog, logical_id, path)
    return catalog


def load_config(catalog: Catalog, config_id: str) -> ModelConfigDocument:
    cached = catalog.configs_cache.get(config_id)
    if cached is not None:
        return cached
    path = catalog.configs.get(config_id)
    if path is None:
        raise ReferenceError(f"Unknown config ID: {config_id}")
    document = _parse_document(path, ModelConfigDocument)
    if document.id != config_id:
        raise ReferenceError(f"Config reference ID {config_id!r} does not match {document.id!r}", path)
    catalog.document_paths.add(path)
    catalog.configs_cache[config_id] = document
    return document


def _load_artifact(catalog: Catalog, path: Path, expected_id: str, expected_kind: str, text: str) -> AutoLabelArtifact:
    if expected_kind != "autolabels":
        raise ReferenceError(f"Unsupported artifact kind: {expected_kind}", path)
    document = _parse_document(path, AutoLabelsDocument)
    if document.id != expected_id or document.kind != expected_kind:
        raise ReferenceError("Artifact reference does not match artifact document", path)
    _register(catalog, document.id, path)
    load_config(catalog, document.producer.config)
    for label in document.labels:
        if label.start >= label.end or label.end > len(text) or text[label.start : label.end] != label.text:
            raise TestDataError(f"Autolabel {label.text!r} has invalid bounds for {path}")
    catalog.document_paths.add(path)
    return AutoLabelArtifact(
        id=document.id,
        producer_name=document.producer.name,
        config_id=document.producer.config,
        labels=tuple(document.labels),
        errors=tuple(document.errors),
        path=path,
    )


def _load_version(catalog: Catalog, path: Path, expected_id: str) -> ContentVersionDataset:
    document = _parse_document(path, ContentVersionManifestDocument)
    if document.id != expected_id:
        raise ReferenceError("Content-version reference ID does not match manifest", path)
    _register(catalog, document.id, path)
    text_path = _resolve(path.parent, document.text, catalog.root)
    text = text_path.read_text(encoding="utf-8").removesuffix("\n")
    artifacts = tuple(
        _load_artifact(
            catalog,
            _resolve(path.parent, ref.path, catalog.root),
            ref.id,
            ref.kind,
            text,
        )
        for ref in document.artifacts
    )
    catalog.document_paths.add(path)
    catalog.content_paths.add(text_path)
    return ContentVersionDataset(document.id, document.number, text, artifacts, path)


def _load_chapter(catalog: Catalog, path: Path, expected_id: str, expected_number: int) -> ChapterDataset:
    document = _parse_document(path, ChapterManifestDocument)
    if document.id != expected_id or document.number != expected_number:
        raise ReferenceError("Chapter reference does not match chapter manifest", path)
    _register(catalog, document.id, path)
    versions = tuple(
        _load_version(catalog, _resolve(path.parent, ref.path, catalog.root), ref.id) for ref in document.versions
    )
    numbers = sorted(version.number for version in versions)
    if numbers != list(range(1, len(numbers) + 1)):
        raise TestDataError(f"Chapter versions must be contiguous from 1: {document.id}")
    catalog.document_paths.add(path)
    return ChapterDataset(document.id, document.number, document.title, document.is_public, versions, path)


def load_novel(catalog: Catalog, novel_id: str) -> NovelDataset:
    cached = catalog.novels_cache.get(novel_id)
    if cached is not None:
        return cached
    path = catalog.novels.get(novel_id)
    if path is None:
        raise ReferenceError(f"Unknown novel ID: {novel_id}")
    document = _parse_document(path, NovelManifestDocument)
    if document.id != novel_id:
        raise ReferenceError("Novel reference ID does not match novel manifest", path)
    chapters = tuple(
        _load_chapter(catalog, _resolve(path.parent, ref.path, catalog.root), ref.id, ref.number)
        for ref in document.chapters
    )
    chapter_numbers = [chapter.number for chapter in chapters]
    if len(chapter_numbers) != len(set(chapter_numbers)):
        raise TestDataError(f"Novel has duplicate chapter numbers: {novel_id}")
    catalog.document_paths.add(path)
    novel = NovelDataset(
        id=document.id,
        title=document.title,
        description=document.description,
        author=document.author,
        language_code=document.language_code,
        novel_type=document.novel_type,
        visibility=document.visibility,
        provenance=document.provenance,
        chapters=chapters,
        path=path,
    )
    catalog.novels_cache[novel_id] = novel
    return novel


def load_relation(catalog: Catalog, relation_id: str) -> RelationBundleDocument:
    cached = catalog.relations_cache.get(relation_id)
    if cached is not None:
        return cached
    path = catalog.relations.get(relation_id)
    if path is None:
        raise ReferenceError(f"Unknown relation ID: {relation_id}")
    document = _parse_document(path, RelationBundleDocument)
    if document.id != relation_id:
        raise ReferenceError("Relation reference ID does not match relation document", path)
    known_novels = set(catalog.novels)
    for source_work in document.source_works:
        unknown = set(source_work.novels) - known_novels
        if unknown:
            raise ReferenceError(f"Source work references unknown novels: {sorted(unknown)}", path)
        for novel_id in source_work.novels:
            load_novel(catalog, novel_id)
    catalog.document_paths.add(path)
    catalog.relations_cache[relation_id] = document
    return document
