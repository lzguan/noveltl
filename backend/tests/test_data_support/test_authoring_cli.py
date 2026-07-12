import json
import shutil
import sys
from pathlib import Path

from scripts.add_test_novel import main as add_novel_main
from scripts.generate_test_autolabels import main as generate_autolabels_main

DATASET_ROOT = Path(__file__).parents[1] / "test_data" / "datasets" / "synthetic-smoke"


def test_add_novel_cli_dry_run(tmp_path: Path, monkeypatch, capsys) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    input_dir.joinpath("novel.json").write_text(
        json.dumps(
            {
                "$schema": "novel-input.schema.json",
                "schemaVersion": 1,
                "title": "CLI Novel",
                "languageCode": "zh",
                "novelType": "original",
                "visibility": "public",
                "provenance": {"kind": "synthetic", "creator": "tests", "license": "test"},
            }
        ),
        encoding="utf-8",
    )
    input_dir.joinpath("chapter-0002.txt").write_text("第二章。", encoding="utf-8")
    dataset = tmp_path / "dataset"
    shutil.copytree(DATASET_ROOT, dataset)
    monkeypatch.setattr(
        sys,
        "argv",
        ["add_test_novel", str(input_dir), str(dataset), "--no-id", "--dry-run"],
    )

    add_novel_main()

    assert capsys.readouterr().out == "Would add novel: cli-novel\n"
    assert not dataset.joinpath("novels/cli-novel").exists()


def test_generate_autolabels_cli_dry_run(tmp_path: Path, monkeypatch, capsys) -> None:
    dataset = tmp_path / "dataset"
    shutil.copytree(DATASET_ROOT, dataset)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_test_autolabels",
            str(dataset),
            "xianxia-source",
            "--config",
            "cluener-default",
            "--chapters",
            "1",
            "--version",
            "2",
            "--force",
            "--dry-run",
        ],
    )

    generate_autolabels_main()

    assert capsys.readouterr().out == "Would generate 1 autolabel artifact(s).\n"
