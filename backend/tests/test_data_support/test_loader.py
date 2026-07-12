import shutil
from pathlib import Path

import pytest

from test_support.test_data import load_catalog, load_novel, load_relation
from test_support.test_data.errors import TestDataError as InvalidTestDataError

DATASET_ROOT = Path(__file__).parents[1] / "test_data" / "datasets" / "synthetic-smoke"


def test_catalog_load_is_lazy() -> None:
    catalog = load_catalog(DATASET_ROOT)

    assert set(catalog.novels) == {"xianxia-source", "xianxia-translation"}
    assert catalog.novels_cache == {}
    assert catalog.document_paths == {DATASET_ROOT.resolve() / "catalog.json"}


def test_novel_loads_ordered_versions_and_artifacts() -> None:
    catalog = load_catalog(DATASET_ROOT)

    novel = load_novel(catalog, "xianxia-source")
    chapter = novel.chapters[0]

    assert [version.number for version in chapter.versions] == [1, 2]
    assert chapter.versions[-1].text == "清晨，林安来到青石城。\n他开始修炼。"
    assert chapter.versions[-1].artifacts[0].config_id == "cluener-default"
    assert "cluener-default" in catalog.configs_cache


def test_relation_loads_its_novel_dependencies() -> None:
    catalog = load_catalog(DATASET_ROOT)

    relation = load_relation(catalog, "translation-pair")

    assert relation.source_works[0].novels == ["xianxia-source", "xianxia-translation"]
    assert set(catalog.novels_cache) == {"xianxia-source", "xianxia-translation"}


def test_artifact_offsets_are_validated(tmp_path: Path) -> None:
    artifact_path = DATASET_ROOT / (
        "novels/xianxia-source/chapters/chapter-0001/versions/v0002/autolabels.cluener.json"
    )
    original = artifact_path.read_text(encoding="utf-8")

    # A copied manifest is used so the committed dataset remains immutable during the test.
    copied_root = tmp_path / "copy"
    shutil.copytree(DATASET_ROOT, copied_root)
    copied_artifact = copied_root / artifact_path.relative_to(DATASET_ROOT)
    copied_artifact.write_text(original.replace('"text": "林安"', '"text": "错误"', 1), encoding="utf-8")

    with pytest.raises(InvalidTestDataError, match="invalid bounds"):
        load_novel(load_catalog(copied_root), "xianxia-source")
