import json
import shutil
from pathlib import Path

import pytest

from test_support.test_data import load_catalog, load_novel
from test_support.test_data.authoring import add_novel, generate_autolabels, parse_chapters
from test_support.test_data.errors import TestDataError as InvalidTestDataError
from test_support.test_data.formats.v1.documents import AutoLabel
from test_support.test_data.lockfile import check_lock

DATASET_ROOT = Path(__file__).parents[1] / "test_data" / "datasets" / "synthetic-smoke"


@pytest.fixture
def dataset_copy(tmp_path: Path) -> Path:
    result = tmp_path / "synthetic-smoke"
    shutil.copytree(DATASET_ROOT, result)
    return result


def _write_input(path: Path, *, novel_id: str | None = "new-novel", title: str = "New Novel") -> None:
    value = {
        "$schema": "novel-input.schema.json",
        "schemaVersion": 1,
        "title": title,
        "description": None,
        "author": None,
        "languageCode": "zh",
        "novelType": "original",
        "visibility": "public",
        "provenance": {"kind": "synthetic", "creator": "tests", "license": "project-test-fixture"},
        "chapters": {"3": {"title": "Third", "isPublic": False}},
    }
    if novel_id is not None:
        value["id"] = novel_id
    path.mkdir()
    path.joinpath("novel.json").write_text(json.dumps(value), encoding="utf-8")
    path.joinpath("chapter-0001.txt").write_text("第一章。", encoding="utf-8")
    path.joinpath("chapter-0003.txt").write_text("第三章。", encoding="utf-8")


def test_add_novel_supports_sparse_chapters_and_overrides(dataset_copy: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    _write_input(input_dir)

    assert add_novel(input_dir, dataset_copy) == "new-novel"

    novel = load_novel(load_catalog(dataset_copy), "new-novel")
    assert [chapter.number for chapter in novel.chapters] == [1, 3]
    assert novel.chapters[0].title == "Chapter 1"
    assert novel.chapters[1].title == "Third"
    assert novel.chapters[1].is_public is False
    assert novel.chapters[0].versions[0].number == 1
    check_lock(dataset_copy, ["novels/new-novel"])


def test_add_novel_dry_run_generates_stable_non_ascii_id(dataset_copy: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    _write_input(input_dir, novel_id=None, title="青石城")

    novel_id = add_novel(input_dir, dataset_copy, no_id=True, dry_run=True)

    assert novel_id.startswith("novel-")
    assert len(novel_id) == 14
    assert not dataset_copy.joinpath("novels", novel_id).exists()


def test_add_novel_requires_explicit_no_id_mode(dataset_copy: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    _write_input(input_dir, novel_id=None)

    with pytest.raises(InvalidTestDataError, match="must include id"):
        add_novel(input_dir, dataset_copy)


def test_add_novel_rejects_unsafe_explicit_id(dataset_copy: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    _write_input(input_dir, novel_id="../outside")

    with pytest.raises(InvalidTestDataError, match="Could not validate novel input"):
        add_novel(input_dir, dataset_copy)


def test_parse_chapter_selector() -> None:
    assert parse_chapters("1,3-5") == {1, 3, 4, 5}


def test_generate_autolabels_skips_existing_and_force_replaces(dataset_copy: Path) -> None:
    calls = 0

    def predict(text: str, config: object) -> tuple[list[AutoLabel], list[dict[str, object]]]:
        nonlocal calls
        calls += 1
        return [AutoLabel(start=3, end=5, text=text[3:5], entity_group="person", score=0.5)], []

    skipped = generate_autolabels(
        dataset_copy,
        "xianxia-source",
        "cluener-default",
        chapters={1},
        version=2,
        predictor=predict,
    )
    generated = generate_autolabels(
        dataset_copy,
        "xianxia-source",
        "cluener-default",
        chapters={1},
        version=2,
        force=True,
        predictor=predict,
    )

    assert skipped == 0
    assert generated == 1
    assert calls == 1
    artifact = load_novel(load_catalog(dataset_copy), "xianxia-source").chapters[0].versions[1].artifacts[0]
    assert artifact.labels[0].score == 0.5
    check_lock(dataset_copy, ["novels/xianxia-source"])


def test_generate_autolabels_dry_run_does_not_call_predictor(dataset_copy: Path) -> None:
    def fail_predictor(text: str, config: object) -> tuple[list[AutoLabel], list[dict[str, object]]]:
        raise AssertionError("dry run loaded the model")

    count = generate_autolabels(
        dataset_copy,
        "xianxia-source",
        "cluener-default",
        chapters={1},
        version=2,
        force=True,
        dry_run=True,
        predictor=fail_predictor,
    )

    assert count == 1
