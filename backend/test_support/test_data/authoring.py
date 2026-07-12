import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from .domain import AutoLabelArtifact, ContentVersionDataset
from .errors import ReferenceError, TestDataError
from .formats.v1.documents import (
    ArtifactReference,
    AutoLabel,
    AutoLabelsDocument,
    CatalogDocument,
    ContentVersionManifestDocument,
    ModelConfigDocument,
    NovelInputDocument,
    Reference,
)
from .loader import load_catalog, load_config, load_novel
from .lockfile import LOCK_NAME, write_lock

CHAPTER_PATTERN = re.compile(r"chapter-(\d{4})\.txt")
SAFE_ID_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
ChapterPrediction = tuple[list[AutoLabel], list[dict[str, Any]]]
Predictor = Callable[[str, object], ChapterPrediction]


def _write_json(path: Path, value: object) -> None:
    if isinstance(value, BaseModel):
        rendered = value.model_dump_json(by_alias=True, exclude_none=False, indent=2) + "\n"
    else:
        rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def _schema_uri(destination: Path, catalog_root: Path, filename: str) -> str:
    schema = Path(__file__).resolve().parents[2] / "tests" / "test_data" / "schema" / "v1" / "json" / filename
    return Path(os.path.relpath(schema, destination.parent)).as_posix()


def _slug(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if slug:
        return slug
    digest = hashlib.sha256(title.encode()).hexdigest()[:8]
    return f"novel-{digest}"


def _read_novel_input(input_dir: Path) -> NovelInputDocument:
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


def add_novel(input_dir: Path | str, catalog_root: Path | str, *, no_id: bool = False, dry_run: bool = False) -> str:
    source = Path(input_dir).resolve()
    root = Path(catalog_root).resolve()
    metadata = _read_novel_input(source)
    if no_id and metadata.id is not None:
        raise TestDataError("novel.json must omit id when --no-id is used")
    if not no_id and metadata.id is None:
        raise TestDataError("novel.json must include id unless --no-id is used")
    novel_id = _slug(metadata.title) if no_id else metadata.id
    if novel_id is None:
        raise TestDataError("Could not resolve novel ID")
    chapters = _chapter_files(source)
    unknown_overrides = set(metadata.chapters) - {number for number, _ in chapters}
    if unknown_overrides:
        raise TestDataError(f"Chapter overrides reference missing files: {sorted(unknown_overrides)}")

    catalog = load_catalog(root)
    destination = root / "novels" / novel_id
    if novel_id in catalog.novels or destination.exists():
        raise TestDataError(f"Novel already exists: {novel_id}")
    if dry_run:
        return novel_id

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix=f".{novel_id}-", dir=destination.parent))
    staged_novel = stage_root / novel_id
    catalog_path = root / "catalog.json"
    original_catalog = catalog_path.read_text(encoding="utf-8")
    try:
        chapter_refs: list[dict[str, object]] = []
        for number, text_source in chapters:
            chapter_name = f"chapter-{number:04d}"
            chapter_id = f"{novel_id}-{chapter_name}"
            version_id = f"{chapter_id}-v0001"
            version_dir = staged_novel / "chapters" / chapter_name / "versions" / "v0001"
            final_version_dir = destination / "chapters" / chapter_name / "versions" / "v0001"
            text = text_source.read_text(encoding="utf-8")
            version_manifest = {
                "$schema": _schema_uri(
                    final_version_dir / "manifest.json", root, "content-version-manifest.schema.json"
                ),
                "kind": "contentVersionManifest",
                "schemaVersion": 1,
                "id": version_id,
                "number": 1,
                "text": "text.txt",
                "artifacts": [],
            }
            override = metadata.chapters.get(number)
            chapter_dir = version_dir.parents[1]
            final_chapter_dir = final_version_dir.parents[1]
            _write_json(version_dir / "manifest.json", version_manifest)
            version_dir.joinpath("text.txt").write_text(text, encoding="utf-8")
            _write_json(
                chapter_dir / "manifest.json",
                {
                    "$schema": _schema_uri(
                        final_chapter_dir / "manifest.json", root, "chapter-manifest.schema.json"
                    ),
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

        manifest_path = staged_novel / "manifest.json"
        _write_json(
            manifest_path,
            {
                "$schema": _schema_uri(destination / "manifest.json", root, "novel-manifest.schema.json"),
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
        catalog_doc = CatalogDocument.model_validate_json(original_catalog)
        catalog_doc.novels.append(Reference(id=novel_id, path=f"novels/{novel_id}/manifest.json"))
        catalog_doc.novels.sort(key=lambda item: item.id)
        _write_json(catalog_path, catalog_doc)
        write_lock(root, [f"novels/{novel_id}"] if (root / LOCK_NAME).exists() else None)
    except Exception:
        catalog_path.write_text(original_catalog, encoding="utf-8")
        if destination.exists():
            shutil.rmtree(destination)
        raise
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)
    return novel_id


def parse_chapters(value: str) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError("Chapter range start exceeds end")
            result.update(range(start, end + 1))
        else:
            result.add(int(part))
    if not result or min(result) < 1:
        raise ValueError("Chapter numbers must be positive")
    return result


def _make_default_predictor(config: ModelConfigDocument) -> Predictor:
    from src.autolabels.constants import SepPriority
    from src.autolabels.params import CluenerParams
    from src.autolabels.worker.inference import Cluener

    sep_map = {"high": SepPriority.HIGH, "med": SepPriority.MED, "low": SepPriority.LOW}
    params = CluenerParams(
        chunk_size=config.parameters.chunk_size,
        force_chunk=config.parameters.force_chunk,
        separators={key: sep_map[value] for key, value in config.parameters.separators.items()},
    )
    model = Cluener().model
    if not model.is_deterministic:
        raise TestDataError("Test-data autolabel models must be deterministic")

    def predict(text: str, config_value: object) -> ChapterPrediction:
        labels, errors = model.predict(text, params)
        return (
            [
                AutoLabel(
                    start=label.label_start,
                    end=label.label_end,
                    text=label.label_word,
                    entity_group=label.label_entity_group,
                    score=label.label_score,
                )
                for label in labels
            ],
            list(errors),
        )

    return predict


def generate_autolabels(
    catalog_root: Path | str,
    novel_id: str,
    config_id: str,
    *,
    chapters: set[int] | None = None,
    version: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    predictor: Predictor | None = None,
) -> int:
    root = Path(catalog_root).resolve()
    catalog = load_catalog(root)
    config = load_config(catalog, config_id)
    novel = load_novel(catalog, novel_id)
    if SAFE_ID_PATTERN.fullmatch(config_id) is None:
        raise TestDataError(f"Config ID is not safe for artifact filenames: {config_id}")
    if config.model_name != "cluener":
        raise TestDataError(f"Unsupported autolabel model: {config.model_name}")
    available = {chapter.number for chapter in novel.chapters}
    selected = available if chapters is None else chapters
    missing = selected - available
    if missing:
        raise TestDataError(f"Selected chapters do not exist: {sorted(missing)}")

    targets = []
    for chapter in novel.chapters:
        if chapter.number not in selected:
            continue
        matches = [item for item in chapter.versions if version is None or item.number == version]
        if not matches:
            raise TestDataError(f"Chapter {chapter.number} has no content version {version}")
        content = max(matches, key=lambda item: item.number)
        existing = next((item for item in content.artifacts if item.config_id == config_id), None)
        artifact_id = existing.id if existing is not None else f"{content.id}-autolabels-{config_id}"
        if existing is not None and not force:
            continue
        targets.append((content, artifact_id, existing))
    if dry_run:
        return len(targets)

    predict = predictor or _make_default_predictor(config)
    generated: list[tuple[ContentVersionDataset, str, AutoLabelArtifact | None, ChapterPrediction]] = []
    for content, artifact_id, existing in targets:
        prediction = predict(content.text, config)
        for label in prediction[0]:
            if label.start >= label.end or label.end > len(content.text) or content.text[label.start : label.end] != label.text:
                raise TestDataError(f"Generated autolabel {label.text!r} has invalid bounds")
        generated.append((content, artifact_id, existing, prediction))

    originals: dict[Path, str | None] = {}
    try:
        for content, artifact_id, existing, (labels, errors) in generated:
            artifact_path = (
                existing.path if existing is not None else content.path.parent / f"autolabels.{config_id}.json"
            )
            originals.setdefault(
                artifact_path, artifact_path.read_text(encoding="utf-8") if artifact_path.exists() else None
            )
            originals.setdefault(content.path, content.path.read_text(encoding="utf-8"))
            document = AutoLabelsDocument.model_validate(
                {
                    "$schema": _schema_uri(artifact_path, root, "autolabels.schema.json"),
                    "kind": "autolabels",
                    "schemaVersion": 1,
                    "id": artifact_id,
                    "producer": {"name": config.model_name, "config": config_id},
                    "labels": [label.model_dump(by_alias=True) for label in labels],
                    "errors": errors,
                }
            )
            _write_json(artifact_path, document)
            manifest = ContentVersionManifestDocument.model_validate_json(content.path.read_text(encoding="utf-8"))
            if existing is None:
                manifest.artifacts.append(
                    ArtifactReference(id=artifact_id, kind="autolabels", path=artifact_path.name)
                )
            _write_json(content.path, manifest)
        if generated:
            write_lock(root, [f"novels/{novel_id}"])
    except Exception:
        for path, original in originals.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(original, encoding="utf-8")
        raise
    return len(generated)
