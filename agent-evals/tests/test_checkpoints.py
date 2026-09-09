import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_evals import cli
from agent_evals.checkpoints import create_checkpoint, load_checkpoint, set_expected_memory
from agent_evals.corpora import CorpusImportSpec, import_flat_export
from agent_evals.schemas import Checkpoint, ExpectedMemory
from agent_evals.storage import EvalWorkspace


def workspace_with_corpus(tmp_path: Path) -> EvalWorkspace:
    source = tmp_path / "novel.json"
    source.write_text(
        json.dumps(
            {
                "chapters": [
                    {
                        "chapterNum": number,
                        "chapterTitle": f"Chapter {number}",
                        "chapterContentText": f"Content {number}",
                    }
                    for number in range(1, 6)
                ]
            }
        ),
        encoding="utf-8",
    )
    workspace = EvalWorkspace(tmp_path / "evals")
    workspace.ensure()
    import_flat_export(
        source,
        workspace,
        CorpusImportSpec(id="test-novel", title="Test novel", language_code="zh"),
    )
    return workspace


def test_setting_expected_memory_replaces_same_metric_without_duplication(tmp_path: Path) -> None:
    workspace = workspace_with_corpus(tmp_path)
    checkpoint = Checkpoint.model_validate(
        {
            "id": "opening",
            "corpus": "test-novel",
            "chapters": {"start_inclusive": 1, "end_inclusive": 2},
        }
    )
    create_checkpoint(workspace, checkpoint)

    set_expected_memory(
        workspace,
        checkpoint.id,
        ExpectedMemory(id="identity", memory_type="fact", content="Old identity"),
    )
    set_expected_memory(
        workspace,
        checkpoint.id,
        ExpectedMemory(
            id="identity",
            memory_type="fact",
            category="identity",
            terms=["林渊"],
            content="Current identity",
            lifecycle="supersede",
        ),
    )

    saved = load_checkpoint(workspace, checkpoint.id, validate_context=True)
    assert len(saved.expected_memories) == 1
    assert saved.expected_memories[0].content == "Current identity"
    assert saved.expected_memories[0].terms == ["林渊"]


def test_cli_can_create_and_edit_checkpoint_as_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = workspace_with_corpus(tmp_path)
    monkeypatch.setattr(cli, "_workspace", lambda: workspace)
    runner = CliRunner()

    created = runner.invoke(
        cli.app,
        [
            "checkpoint",
            "create",
            "opening",
            "--corpus",
            "test-novel",
            "--start",
            "1",
            "--end",
            "2",
            "--activity",
            "busy",
        ],
    )
    assert created.exit_code == 0, created.output

    metric = runner.invoke(
        cli.app,
        [
            "checkpoint",
            "metric",
            "set",
            "opening",
            "--id",
            "identity",
            "--memory-type",
            "fact",
            "--category",
            "identity",
            "--term",
            "林渊",
            "--content",
            "The protagonist reveals his identity.",
            "--lifecycle",
            "create",
        ],
    )
    assert metric.exit_code == 0, metric.output

    shown = runner.invoke(cli.app, ["checkpoint", "show", "opening", "--json"])
    assert shown.exit_code == 0, shown.output
    payload = json.loads(shown.output)
    assert payload["chapters"] == {"start_inclusive": 1, "end_inclusive": 2}
    assert payload["expected_memories"][0]["terms"] == ["林渊"]
