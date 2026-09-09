import json
from pathlib import Path

import pytest

from src.datasets.errors import TestDataError as InvalidTestDataError
from test_support.test_data.exporting import (
    build_chapter_upload_v1,
    export_chapter_upload,
    render_chapter_upload,
)

DATA_ROOT = Path(__file__).parents[1] / "test_data"
SYNTHETIC_DATASET_ROOT = DATA_ROOT / "datasets" / "synthetic-smoke"
LEGACY_DATASET_ROOT = DATA_ROOT / "datasets" / "legacy-corpora"
STARFALL_ARTIFACT = DATA_ROOT / "artifacts" / "chapter-upload" / "v1" / "starfall.json"


def test_latest_content_versions_are_exported_by_default() -> None:
    document = build_chapter_upload_v1(SYNTHETIC_DATASET_ROOT, "xianxia-source")

    assert len(document.chapters) == 1
    assert document.chapters[0].chapter_content_text == "清晨，林安来到青石城。\n他开始修炼。"


def test_explicit_content_version_is_exported() -> None:
    document = build_chapter_upload_v1(
        SYNTHETIC_DATASET_ROOT,
        "xianxia-source",
        content_version=1,
    )

    assert document.chapters[0].chapter_content_text == "林安来到青石城。"


def test_missing_content_version_does_not_create_output(tmp_path: Path) -> None:
    output_file = tmp_path / "nested" / "upload.json"

    with pytest.raises(InvalidTestDataError, match="Chapter 1 has no content version 2"):
        export_chapter_upload(
            SYNTHETIC_DATASET_ROOT,
            "xianxia-translation",
            output_file,
            content_version=2,
        )

    assert not output_file.exists()
    assert not output_file.parent.exists()


def test_unsupported_upload_format_is_rejected() -> None:
    with pytest.raises(InvalidTestDataError, match="Unsupported chapter upload format: v2"):
        render_chapter_upload(SYNTHETIC_DATASET_ROOT, "xianxia-source", format_version="v2")


def test_committed_starfall_artifact_matches_exporter() -> None:
    rendered = render_chapter_upload(LEGACY_DATASET_ROOT, "starfall")

    assert STARFALL_ARTIFACT.read_text(encoding="utf-8") == rendered
    assert len(json.loads(rendered)["chapters"]) == 4
