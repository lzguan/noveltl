import shutil
from pathlib import Path

import pytest

from test_support.test_data.errors import LockMismatchError
from test_support.test_data.lockfile import check_lock, read_lock, write_lock

DATASET_ROOT = Path(__file__).parents[1] / "test_data" / "datasets" / "synthetic-smoke"


@pytest.fixture
def dataset_copy(tmp_path: Path) -> Path:
    result = tmp_path / "synthetic-smoke"
    shutil.copytree(DATASET_ROOT, result)
    return result


def test_committed_lock_is_current() -> None:
    check_lock(DATASET_ROOT)


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
