from pathlib import Path

from src.datasets import load_catalog, load_novel
from src.datasets.domain import ContentVersionDataset
from src.datasets.errors import TestDataError
from src.novels.imports import BulkChapterUploadV1, ChapterUpload


def _select_content(
    chapter_number: int,
    versions: tuple[ContentVersionDataset, ...],
    content_version: int | None,
) -> ContentVersionDataset:
    matches = [version for version in versions if content_version is None or version.number == content_version]
    if not matches:
        raise TestDataError(f"Chapter {chapter_number} has no content version {content_version}")
    return max(matches, key=lambda version: version.number)


def build_chapter_upload_v1(
    catalog_root: Path | str,
    novel_id: str,
    *,
    content_version: int | None = None,
) -> BulkChapterUploadV1:
    catalog = load_catalog(Path(catalog_root).resolve())
    novel = load_novel(catalog, novel_id)
    chapters = [
        ChapterUpload(
            chapter_num=chapter.number,
            chapter_title=chapter.title,
            chapter_content_text=_select_content(
                chapter.number,
                chapter.versions,
                content_version,
            ).text,
            chapter_is_public=chapter.is_public,
        )
        for chapter in sorted(novel.chapters, key=lambda chapter: chapter.number)
    ]
    return BulkChapterUploadV1(chapters=chapters)


def render_chapter_upload(
    catalog_root: Path | str,
    novel_id: str,
    *,
    format_version: str = "v1",
    content_version: int | None = None,
) -> str:
    if format_version != "v1":
        raise TestDataError(f"Unsupported chapter upload format: {format_version}")
    document = build_chapter_upload_v1(
        catalog_root,
        novel_id,
        content_version=content_version,
    )
    return _render_v1(document)


def _render_v1(document: BulkChapterUploadV1) -> str:
    return document.model_dump_json(by_alias=True, indent=2) + "\n"


def export_chapter_upload(
    catalog_root: Path | str,
    novel_id: str,
    output_file: Path | str,
    *,
    format_version: str = "v1",
    content_version: int | None = None,
) -> int:
    if format_version != "v1":
        raise TestDataError(f"Unsupported chapter upload format: {format_version}")
    document = build_chapter_upload_v1(catalog_root, novel_id, content_version=content_version)
    destination = Path(output_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_render_v1(document), encoding="utf-8")
    return len(document.chapters)
