import shutil
from pathlib import Path

import pytest

from src.datasets.errors import LockMismatchError
from src.datasets.lockfile import check_lock, compute_lock, read_lock, write_lock

DATASET_ROOT = Path(__file__).parents[1] / "test_data" / "datasets" / "synthetic-smoke"
LEGACY_DATASET_ROOT = DATASET_ROOT.parent / "legacy-corpora"


@pytest.fixture
def dataset_copy(tmp_path: Path) -> Path:
    result = tmp_path / "synthetic-smoke"
    shutil.copytree(DATASET_ROOT, result)
    return result


@pytest.mark.parametrize("dataset_root", [DATASET_ROOT, LEGACY_DATASET_ROOT])
def test_committed_lock_is_current(dataset_root: Path) -> None:
    check_lock(dataset_root)


def test_full_check_accepts_relocated_dataset_without_rewriting_lock(dataset_copy: Path) -> None:
    """Eval runners in other checkouts can verify unchanged shared corpus files."""
    lock_path = dataset_copy / "catalog.lock.json"
    original = lock_path.read_bytes()
    computed, _ = compute_lock(dataset_copy)
    assert read_lock(dataset_copy).schema_uri != computed.schema_uri

    check_lock(dataset_copy)

    assert lock_path.read_bytes() == original


def test_full_check_detects_changed_content(dataset_copy: Path) -> None:
    text_path = dataset_copy / "novels/xianxia-source/chapters/chapter-0001/versions/v0002/text.txt"
    text_path.write_text(text_path.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

    with pytest.raises(LockMismatchError, match="stale"):
        check_lock(dataset_copy)


def test_targeted_update_preserves_unselected_entries(dataset_copy: Path) -> None:
    before = read_lock(dataset_copy)
    text_path = dataset_copy / "novels/xianxia-source/chapters/chapter-0001/versions/v0002/text.txt"
    text_path.write_text(text_path.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")

    write_lock(dataset_copy, ["novels/xianxia-source"])
    after = read_lock(dataset_copy)

    translation_path = "novels/xianxia-translation/manifest.json"
    assert after.files[translation_path] == before.files[translation_path]
    check_lock(dataset_copy, ["novels/xianxia-source"])
