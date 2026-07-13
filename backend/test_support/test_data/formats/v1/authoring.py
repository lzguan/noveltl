import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ...domain import AutoLabelArtifact, ContentVersionDataset
from ...errors import ReferenceError, TestDataError
from ...lockfile import LOCK_NAME, write_lock
from .documents import (
    ArtifactReference,
    AutoLabel,
    AutoLabelsDocument,
    CatalogDocument,
    ContentVersionManifestDocument,
    ModelConfigDocument,
    NovelInputDocument,
    Reference,
)

CHAPTER_PATTERN = re.compile(r"chapter-(\d{4})\.txt")
SAFE_ID_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
GeneratedArtifact = tuple[
    ContentVersionDataset,
    str,
    AutoLabelArtifact | None,
    tuple[list[AutoLabel], list[dict[str, Any]]],
]


def _write_json(path: Path, value: object) -> None:
    if isinstance(value, BaseModel):
        rendered = value.model_dump_json(by_alias=True, exclude_none=False, indent=2) + "\n"
    else:
        rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def _schema_uri(destination: Path, filename: str) -> str:
    schema = Path(__file__).resolve().parents[4] / "tests" / "test_data" / "schema" / "v1" / "json" / filename
    return Path(os.path.relpath(schema, destination.parent)).as_posix()


def _slug(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if slug:
        return slug
    return f"novel-{hashlib.sha256(title.encode()).hexdigest()[:8]}"


def _read_input(input_dir: Path) -> NovelInputDocument:
    path = input_dir / "novel.json"
    try:
        return NovelInputDocument.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ReferenceError("Could not validate novel input", path) from exc


def _chapter_files(input_dir: Path) -> list[tuple[int, Path]]:
    result: list[tuple[int, Path]] = []
    for path in sorted(input_dir.glob("*.txt")):
        match = CHAPTER_PATTERN.fullmatch(path.name)
        if match is None:
            raise ReferenceError("Chapter filename must match chapter-NNNN.txt", path)
        number = int(match.group(1))
        if number < 1:
            raise ReferenceError("Chapter number must be positive", path)
        result.append((number, path))
    if not result:
        raise ReferenceError("Input directory contains no chapter files", input_dir)
    return result


def add_novel(
    input_dir: Path,
    catalog_root: Path,
    existing_novel_ids: set[str],
    *,
    no_id: bool,
    dry_run: bool,
) -> str:
    metadata = _read_input(input_dir)
    if no_id and metadata.id is not None:
        raise TestDataError("novel.json must omit id when --no-id is used")
    if not no_id and metadata.id is None:
        raise TestDataError("novel.json must include id unless --no-id is used")
    novel_id = _slug(metadata.title) if no_id else metadata.id
    if novel_id is None:
        raise TestDataError("Could not resolve novel ID")
    chapters = _chapter_files(input_dir)
    unknown_overrides = set(metadata.chapters) - {number for number, _ in chapters}
    if unknown_overrides:
        raise TestDataError(f"Chapter overrides reference missing files: {sorted(unknown_overrides)}")

    destination = catalog_root / "novels" / novel_id
    if novel_id in existing_novel_ids or destination.exists():
        raise TestDataError(f"Novel already exists: {novel_id}")
    if dry_run:
        return novel_id

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix=f".{novel_id}-", dir=destination.parent))
    staged_novel = stage_root / novel_id
    catalog_path = catalog_root / "catalog.json"
    original_catalog = catalog_path.read_text(encoding="utf-8")
    try:
        chapter_refs: list[dict[str, object]] = []
        for number, text_source in chapters:
            chapter_name = f"chapter-{number:04d}"
            chapter_id = f"{novel_id}-{chapter_name}"
            version_id = f"{chapter_id}-v0001"
            version_dir = staged_novel / "chapters" / chapter_name / "versions" / "v0001"
            final_version_dir = destination / "chapters" / chapter_name / "versions" / "v0001"
            override = metadata.chapters.get(number)
            chapter_dir = version_dir.parents[1]
            final_chapter_dir = final_version_dir.parents[1]
            _write_json(
                version_dir / "manifest.json",
                {
                    "$schema": _schema_uri(final_version_dir / "manifest.json", "content-version-manifest.schema.json"),
                    "kind": "contentVersionManifest",
                    "schemaVersion": 1,
                    "id": version_id,
                    "number": 1,
                    "text": "text.txt",
                    "artifacts": [],
                },
            )
            version_dir.joinpath("text.txt").write_text(text_source.read_text(encoding="utf-8"), encoding="utf-8")
            _write_json(
                chapter_dir / "manifest.json",
                {
                    "$schema": _schema_uri(final_chapter_dir / "manifest.json", "chapter-manifest.schema.json"),
                    "kind": "chapterManifest",
                    "schemaVersion": 1,
                    "id": chapter_id,
                    "number": number,
                    "title": override.title if override and override.title is not None else f"Chapter {number}",
                    "isPublic": override.is_public if override else True,
                    "versions": [{"id": version_id, "path": "versions/v0001/manifest.json"}],
                },
            )
            chapter_refs.append({"id": chapter_id, "number": number, "path": f"chapters/{chapter_name}/manifest.json"})

        _write_json(
            staged_novel / "manifest.json",
            {
                "$schema": _schema_uri(destination / "manifest.json", "novel-manifest.schema.json"),
                "kind": "novelManifest",
                "schemaVersion": 1,
                "id": novel_id,
                "title": metadata.title,
                "description": metadata.description,
                "author": metadata.author,
                "languageCode": metadata.language_code,
                "novelType": metadata.novel_type,
                "visibility": metadata.visibility,
                "provenance": metadata.provenance.model_dump(by_alias=True),
                "chapters": chapter_refs,
            },
        )
        staged_novel.rename(destination)
        catalog = CatalogDocument.model_validate_json(original_catalog)
        catalog.novels.append(Reference(id=novel_id, path=f"novels/{novel_id}/manifest.json"))
        catalog.novels.sort(key=lambda item: item.id)
        _write_json(catalog_path, catalog)
        write_lock(catalog_root, [f"novels/{novel_id}"] if (catalog_root / LOCK_NAME).exists() else None)
    except Exception:
        catalog_path.write_text(original_catalog, encoding="utf-8")
        if destination.exists():
            shutil.rmtree(destination)
        raise
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
    return novel_id


def validate_config_id(config_id: str) -> None:
    if SAFE_ID_PATTERN.fullmatch(config_id) is None:
        raise TestDataError(f"Config ID is not safe for artifact filenames: {config_id}")


def write_autolabels(catalog_root: Path, novel_id: str, config: ModelConfigDocument, generated: list[GeneratedArtifact]) -> None:
    originals: dict[Path, str | None] = {}
    try:
        for content, artifact_id, existing, (labels, errors) in generated:
            artifact_path = existing.path if existing else content.path.parent / f"autolabels.{config.id}.json"
            originals.setdefault(artifact_path, artifact_path.read_text(encoding="utf-8") if artifact_path.exists() else None)
            originals.setdefault(content.path, content.path.read_text(encoding="utf-8"))
            document = AutoLabelsDocument.model_validate(
                {
                    "$schema": _schema_uri(artifact_path, "autolabels.schema.json"),
                    "kind": "autolabels",
                    "schemaVersion": 1,
                    "id": artifact_id,
                    "producer": {"name": config.model_name, "config": config.id},
                    "labels": labels,
                    "errors": errors,
                }
            )
            _write_json(artifact_path, document)
            manifest = ContentVersionManifestDocument.model_validate_json(content.path.read_text(encoding="utf-8"))
            if existing is None:
                manifest.artifacts.append(ArtifactReference(id=artifact_id, kind="autolabels", path=artifact_path.name))
            _write_json(content.path, manifest)
        if generated:
            write_lock(catalog_root, [f"novels/{novel_id}"])
    except Exception:
        for path, original in originals.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(original, encoding="utf-8")
        raise
