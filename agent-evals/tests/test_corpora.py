import json
from pathlib import Path

import pytest
from src.datasets import load_catalog, load_novel
from src.datasets.lockfile import check_lock

from agent_evals.corpora import (
    CorpusImportError,
    CorpusImportSpec,
    import_catalog,
    import_flat_export,
    validate_corpus_id,
)
from agent_evals.storage import EvalWorkspace


def flat_export() -> dict[str, object]:
    return {
        "chapters": [
            {
                "chapterNum": 3,
                "chapterTitle": "第三章",
                "chapterIsPublic": False,
                "chapterContentText": "林渊抵达青石城。",
            },
            {
                "chapterNum": 10_000,
                "chapterTitle": None,
                "chapterIsPublic": True,
                "chapterContentText": "万年之后。",
            },
        ]
    }


def import_spec() -> CorpusImportSpec:
    return CorpusImportSpec(id="cn-xianxia-001", title="Private evaluation novel", language_code="zh")


def test_flat_export_import_creates_exact_locked_catalog(tmp_path: Path) -> None:
    source = tmp_path / "novel.json"
    source.write_text(json.dumps(flat_export(), ensure_ascii=False), encoding="utf-8")
    workspace = EvalWorkspace(tmp_path / "evals")
    workspace.ensure()

    summary = import_flat_export(source, workspace, import_spec())

    assert summary.id == "cn-xianxia-001"
    assert summary.chapter_count == 2
    assert summary.first_chapter == 3
    assert summary.last_chapter == 10_000
    assert len(summary.fingerprint) == 64
    check_lock(summary.path)
    novel = load_novel(load_catalog(summary.path), summary.novel_id)
    assert [chapter.number for chapter in novel.chapters] == [3, 10_000]
    assert novel.chapters[0].versions[0].text == "林渊抵达青石城。"
    assert novel.chapters[1].is_public is True


def test_flat_export_rejects_duplicate_chapter_numbers(tmp_path: Path) -> None:
    payload = flat_export()
    chapters = payload["chapters"]
    assert isinstance(chapters, list)
    chapters.append(chapters[0])
    source = tmp_path / "novel.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    workspace = EvalWorkspace(tmp_path / "evals")

    with pytest.raises(CorpusImportError, match="chapter numbers must be unique"):
        import_flat_export(source, workspace, import_spec())


def test_flat_import_does_not_overwrite_existing_corpus(tmp_path: Path) -> None:
    source = tmp_path / "novel.json"
    source.write_text(json.dumps(flat_export(), ensure_ascii=False), encoding="utf-8")
    workspace = EvalWorkspace(tmp_path / "evals")
    destination = workspace.novels / "cn-xianxia-001"
    destination.mkdir(parents=True)
    destination.joinpath("private.txt").write_text("preserve me", encoding="utf-8")

    with pytest.raises(CorpusImportError, match="already exists"):
        import_flat_export(source, workspace, import_spec())

    assert destination.joinpath("private.txt").read_text(encoding="utf-8") == "preserve me"


def test_existing_single_novel_catalog_import_preserves_fingerprint(tmp_path: Path) -> None:
    source = tmp_path / "novel.json"
    source.write_text(json.dumps(flat_export(), ensure_ascii=False), encoding="utf-8")
    source_workspace = EvalWorkspace(tmp_path / "source-evals")
    source_workspace.ensure()
    source_summary = import_flat_export(source, source_workspace, import_spec())
    destination_workspace = EvalWorkspace(tmp_path / "destination-evals")
    destination_workspace.ensure()

    imported = import_catalog(source_summary.path, destination_workspace, "copied-corpus")

    assert imported.id == "copied-corpus"
    assert imported.novel_id == "cn-xianxia-001"
    assert imported.fingerprint == source_summary.fingerprint
    check_lock(imported.path)


@pytest.mark.parametrize("corpus_id", ["../outside", "UPPERCASE", "contains spaces"])
def test_corpus_id_rejects_unsafe_directory_names(corpus_id: str) -> None:
    with pytest.raises(CorpusImportError, match="corpus ID"):
        validate_corpus_id(corpus_id)
