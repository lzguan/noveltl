import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from pydantic import Field
from src.datasets import initialize_catalog, load_catalog
from src.datasets.authoring import add_novel
from src.datasets.formats.v1.documents import ChapterInput, NovelInputDocument, NovelManifestDocument, Provenance
from src.datasets.lockfile import check_lock, read_lock, write_lock
from src.novels.imports import BulkChapterUploadV1

from agent_evals.schemas import EvalModel
from agent_evals.storage import EvalWorkspace


class CorpusImportError(ValueError):
    """A corpus could not be imported without overwriting or losing data."""


CORPUS_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def validate_corpus_id(value: str) -> str:
    if CORPUS_ID_PATTERN.fullmatch(value) is None:
        raise CorpusImportError("corpus ID must contain only lowercase letters, digits, and internal hyphens")
    return value


class CorpusImportSpec(EvalModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
    title: str = Field(min_length=1)
    language_code: str = Field(min_length=1)
    description: str | None = None
    author: str | None = None
    novel_type: Literal["original", "translation", "other"] = "original"
    visibility: Literal["private", "restricted", "unlisted", "public"] = "private"
    provenance_kind: str = Field(default="private", min_length=1)
    provenance_creator: str = Field(default="local", min_length=1)
    provenance_license: str = Field(default="untracked-private", min_length=1)


@dataclass(frozen=True)
class CorpusSummary:
    id: str
    path: Path
    novel_id: str
    title: str
    language_code: str
    chapter_count: int
    first_chapter: int
    last_chapter: int
    fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "path": str(self.path),
            "novelId": self.novel_id,
            "title": self.title,
            "languageCode": self.language_code,
            "chapterCount": self.chapter_count,
            "firstChapter": self.first_chapter,
            "lastChapter": self.last_chapter,
            "fingerprint": self.fingerprint,
        }


def _fingerprint(catalog_root: Path) -> str:
    lock = read_lock(catalog_root)
    payload = {
        path: entry.model_dump(mode="json", by_alias=True, exclude_none=True)
        for path, entry in sorted(lock.files.items())
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def inspect_corpus(
    path: Path,
    *,
    corpus_id: str | None = None,
    verify_lock: bool = False,
) -> CorpusSummary:
    root = path.resolve()
    if verify_lock:
        check_lock(root)
    catalog = load_catalog(root)
    if len(catalog.novels) != 1:
        raise CorpusImportError("an evaluation corpus must contain exactly one novel")
    novel_id = next(iter(catalog.novels))
    manifest_path = catalog.novels[novel_id]
    try:
        manifest = NovelManifestDocument.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CorpusImportError(f"Could not validate novel manifest: {manifest_path}") from exc
    if manifest.id != novel_id:
        raise CorpusImportError("catalog novel ID does not match its manifest")
    if not manifest.chapters:
        raise CorpusImportError("an evaluation corpus must contain at least one chapter")
    numbers = [chapter.number for chapter in manifest.chapters]
    return CorpusSummary(
        id=corpus_id or root.name,
        path=root,
        novel_id=novel_id,
        title=manifest.title,
        language_code=manifest.language_code,
        chapter_count=len(manifest.chapters),
        first_chapter=min(numbers),
        last_chapter=max(numbers),
        fingerprint=_fingerprint(root),
    )


def discover_corpora(workspace: EvalWorkspace) -> list[CorpusSummary]:
    workspace.ensure()
    summaries = [
        inspect_corpus(path, corpus_id=path.name)
        for path in workspace.novels.iterdir()
        if path.is_dir() and (path / "catalog.json").is_file()
    ]
    return sorted(summaries, key=lambda summary: summary.id.casefold())


def resolve_corpus(workspace: EvalWorkspace, value: str) -> Path:
    candidate = Path(value)
    if candidate.exists():
        return candidate.resolve()
    return (workspace.novels / value).resolve()


def _load_bulk_chapter_upload(source: Path) -> BulkChapterUploadV1:
    try:
        document = BulkChapterUploadV1.model_validate_json(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CorpusImportError(f"Could not validate bulk chapter upload: {source}") from exc
    numbers = [chapter.chapter_num for chapter in document.chapters]
    if len(numbers) != len(set(numbers)):
        raise CorpusImportError("chapter numbers must be unique")
    return document


def _write_authoring_input(root: Path, document: BulkChapterUploadV1, spec: CorpusImportSpec) -> None:
    metadata = NovelInputDocument.model_validate(
        {
            "$schema": "novel-input.schema.json",
            "schemaVersion": 1,
            "id": spec.id,
            "title": spec.title,
            "description": spec.description,
            "author": spec.author,
            "languageCode": spec.language_code,
            "novelType": spec.novel_type,
            "visibility": spec.visibility,
            "provenance": Provenance(
                kind=spec.provenance_kind,
                creator=spec.provenance_creator,
                license=spec.provenance_license,
            ),
            "chapters": {
                chapter.chapter_num: ChapterInput(
                    title=chapter.chapter_title,
                    is_public=chapter.chapter_is_public,
                )
                for chapter in document.chapters
            },
        }
    )
    root.joinpath("novel.json").write_text(
        metadata.model_dump_json(by_alias=True, exclude_none=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for chapter in document.chapters:
        root.joinpath(f"chapter-{chapter.chapter_num:04d}.txt").write_text(
            chapter.chapter_content_text,
            encoding="utf-8",
        )


def import_flat_export(source: Path, workspace: EvalWorkspace, spec: CorpusImportSpec) -> CorpusSummary:
    document = _load_bulk_chapter_upload(source.resolve())
    destination = workspace.novels / spec.id
    if destination.exists():
        raise CorpusImportError(f"Corpus already exists: {spec.id}")

    try:
        initialize_catalog(destination)
        with TemporaryDirectory(prefix=f"agent-eval-{spec.id}-") as temporary:
            authoring_input = Path(temporary)
            _write_authoring_input(authoring_input, document, spec)
            add_novel(authoring_input, destination)
        return inspect_corpus(destination, corpus_id=spec.id)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise


def import_catalog(source: Path, workspace: EvalWorkspace, corpus_id: str) -> CorpusSummary:
    validate_corpus_id(corpus_id)
    source_root = source.resolve()
    inspect_corpus(source_root, corpus_id=corpus_id, verify_lock=True)
    destination = workspace.novels / corpus_id
    if destination.exists():
        raise CorpusImportError(f"Corpus already exists: {corpus_id}")

    try:
        shutil.copytree(source_root, destination)
        write_lock(destination)
        return inspect_corpus(destination, corpus_id=corpus_id)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise


def import_corpus(
    source: Path,
    workspace: EvalWorkspace,
    *,
    corpus_id: str,
    flat_spec: CorpusImportSpec | None = None,
) -> CorpusSummary:
    validate_corpus_id(corpus_id)
    if source.is_dir():
        return import_catalog(source, workspace, corpus_id)
    if flat_spec is None:
        raise CorpusImportError("title and language code are required when importing a bulk chapter upload")
    if flat_spec.id != corpus_id:
        raise CorpusImportError("corpus ID and flat import ID must match")
    return import_flat_export(source, workspace, flat_spec)
