import hashlib
import json
import os
from pathlib import Path

from pydantic import ValidationError

from .domain import Catalog
from .errors import LockMismatchError, ReferenceError
from .formats.v1.documents import CatalogLockDocument, LockFileEntry, LockInputs
from .loader import load_catalog, load_config, load_novel, load_relation

LOCK_NAME = "catalog.lock.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(catalog: Catalog, path: Path) -> str:
    return path.relative_to(catalog.root).as_posix()


def _owner(path: Path, category: str) -> Path:
    return path.parent if category == "novels" else path


def _overlaps(target: Path, owner: Path) -> bool:
    return target == owner or target in owner.parents or owner in target.parents


def _resolve_targets(catalog: Catalog, targets: list[str]) -> tuple[list[Path], set[str]]:
    resolved: list[Path] = []
    matched_categories: set[str] = set()
    for raw in targets:
        if Path(raw).is_absolute():
            raise ReferenceError("Lock target must be relative to the dataset root", Path(raw))
        target = (catalog.root / raw).resolve()
        try:
            target.relative_to(catalog.root)
        except ValueError as exc:
            raise ReferenceError("Lock target escapes dataset root", target) from exc
        if not target.exists():
            raise ReferenceError("Lock target does not exist", target)
        matched = False
        for category in ("configs", "novels", "relations"):
            mapping: dict[str, Path] = getattr(catalog, category)
            for path in mapping.values():
                if _overlaps(target, _owner(path, category)):
                    matched = True
                    matched_categories.add(category)
        if not matched:
            raise ReferenceError("Lock target is not reachable from the catalog", target)
        resolved.append(target)
    return sorted(set(resolved)), matched_categories


def _load_selection(catalog: Catalog, targets: list[str] | None) -> list[Path]:
    if targets is None:
        for config_id in sorted(catalog.configs):
            load_config(catalog, config_id)
        for novel_id in sorted(catalog.novels):
            load_novel(catalog, novel_id)
        for relation_id in sorted(catalog.relations):
            load_relation(catalog, relation_id)
        return [catalog.root]

    resolved, categories = _resolve_targets(catalog, targets)
    for category in ("configs", "novels", "relations"):
        mapping: dict[str, Path] = getattr(catalog, category)
        for logical_id, path in sorted(mapping.items()):
            if not any(_overlaps(target, _owner(path, category)) for target in resolved):
                continue
            if category == "configs":
                load_config(catalog, logical_id)
            elif category == "novels":
                load_novel(catalog, logical_id)
            else:
                load_relation(catalog, logical_id)
    if "configs" in categories:
        # Derived artifacts are reverse dependencies of their model configuration.
        for novel_id in sorted(catalog.novels):
            load_novel(catalog, novel_id)
    return resolved


def compute_lock(root: Path | str, targets: list[str] | None = None) -> tuple[CatalogLockDocument, list[Path]]:
    catalog = load_catalog(root)
    selected_roots = _load_selection(catalog, targets)
    entries: dict[str, LockFileEntry] = {}
    for path in sorted(catalog.document_paths | catalog.content_paths):
        relative = _relative(catalog, path)
        if path in catalog.content_paths:
            kind = "chapterText"
        else:
            raw = json.loads(path.read_text(encoding="utf-8"))
            kind = str(raw["kind"])
        entries[relative] = LockFileEntry(kind=kind, size=path.stat().st_size, sha256=_sha256(path))

    for novel in catalog.novels_cache.values():
        for chapter in novel.chapters:
            for version in chapter.versions:
                text_path = next(path for path in catalog.content_paths if path.parent == version.path.parent)
                text_hash = _sha256(text_path)
                for artifact in version.artifacts:
                    config_path = catalog.configs[artifact.config_id]
                    relative = _relative(catalog, artifact.path)
                    entry = entries[relative]
                    entries[relative] = entry.model_copy(
                        update={"inputs": LockInputs(text_sha256=text_hash, config_sha256=_sha256(config_path))}
                    )

    schema_path = Path(__file__).resolve().parents[2] / "tests" / "test_data" / "schema" / "v1" / "json" / "catalog-lock.schema.json"
    schema_uri = Path(os.path.relpath(schema_path, catalog.root)).as_posix()
    lock = CatalogLockDocument.model_validate(
        {
            "$schema": schema_uri,
            "kind": "testDataLock",
            "schemaVersion": 1,
            "datasetSchemaVersion": catalog.schema_version,
            "files": dict(sorted(entries.items())),
        }
    )
    return lock, selected_roots


def read_lock(root: Path | str) -> CatalogLockDocument:
    path = Path(root).resolve() / LOCK_NAME
    try:
        return CatalogLockDocument.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ReferenceError("Could not read catalog lock", path) from exc


def render_lock(lock: CatalogLockDocument) -> str:
    return lock.model_dump_json(by_alias=True, exclude_none=True, indent=2) + "\n"


def write_lock(root: Path | str, targets: list[str] | None = None) -> CatalogLockDocument:
    dataset_root = Path(root).resolve()
    computed, selected_roots = compute_lock(dataset_root, targets)
    path = dataset_root / LOCK_NAME
    if targets is None:
        result = computed
    else:
        if not path.exists():
            raise ReferenceError("A targeted update requires an existing lock; generate it with --all first", path)
        current = read_lock(dataset_root)
        files = dict(current.files)
        for relative in list(files):
            absolute = dataset_root / relative
            if any(root_path == absolute or root_path in absolute.parents for root_path in selected_roots):
                del files[relative]
        files.update(computed.files)
        result = current.model_copy(update={"files": dict(sorted(files.items()))})
    path.write_text(render_lock(result), encoding="utf-8")
    return result


def check_lock(root: Path | str, targets: list[str] | None = None) -> None:
    dataset_root = Path(root).resolve()
    current = read_lock(dataset_root)
    computed, selected_roots = compute_lock(dataset_root, targets)
    if targets is None:
        if current != computed:
            raise LockMismatchError("catalog.lock.json is stale")
        return
    current_selected = {
        relative: entry
        for relative, entry in current.files.items()
        if any(root_path == dataset_root / relative or root_path in (dataset_root / relative).parents for root_path in selected_roots)
        or relative in computed.files
    }
    if current_selected != computed.files:
        raise LockMismatchError("catalog.lock.json is stale for the selected targets")
