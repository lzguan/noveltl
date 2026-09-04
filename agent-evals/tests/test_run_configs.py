import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_evals import cli
from agent_evals.checkpoints import create_checkpoint
from agent_evals.corpora import CorpusImportSpec, import_flat_export
from agent_evals.run_configs import job_toolsets, load_run_config
from agent_evals.schemas import Checkpoint, RunConfig
from agent_evals.storage import EvalWorkspace


def workspace_with_corpus_and_checkpoint(tmp_path: Path) -> EvalWorkspace:
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
    create_checkpoint(
        workspace,
        Checkpoint.model_validate(
            {
                "id": "opening",
                "corpus": "test-novel",
                "chapters": {"start_inclusive": 1, "end_inclusive": 2},
            }
        ),
    )
    return workspace


def test_cli_lists_toolsets_from_backend_metadata() -> None:
    from src.memory.agent.types import TOOLSET_NAMES

    result = CliRunner().invoke(cli.app, ["config", "toolsets"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == list(TOOLSET_NAMES)


def test_cli_lists_models_from_backend_metadata() -> None:
    from src.memory.agent.types import MODEL_NAMES

    result = CliRunner().invoke(cli.app, ["config", "models"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == list(MODEL_NAMES)


def test_run_config_builds_backend_job_toolset_payload() -> None:
    config = RunConfig.model_validate(
        {
            "id": "retention-config",
            "change": "Configure transformation retention.",
            "objectives": ["Bound active transformation history."],
            "degradation_guardrails": ["Preserve retained occurrences."],
            "decision_rule": "Accept when retention is bounded.",
            "corpus": "test-novel",
            "chapters": {"start_inclusive": 1, "end_inclusive": 5},
            "agent": {
                "model_name": "deepseek:deepseek-v4-flash-low",
                "toolsets": [
                    {"name": "glossary_gender_advanced_events_read"},
                    {
                        "name": "glossary_gender_advanced_events_write",
                        "settings": {"keepFirst": 2, "keepRolling": 4},
                    },
                ],
            },
        }
    )

    assert job_toolsets(config) == {
        "glossary_gender_advanced_events_read": {},
        "glossary_gender_advanced_events_write": {"keepFirst": 2, "keepRolling": 4},
    }


def test_cli_creates_and_updates_context_validated_run_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = workspace_with_corpus_and_checkpoint(tmp_path)
    monkeypatch.setattr(cli, "_workspace", lambda: workspace)
    runner = CliRunner()

    created = runner.invoke(
        cli.app,
        [
            "config",
            "create",
            "single-mark-v1",
            "--change",
            "Restrict retrieval to one mark per call.",
            "--objective",
            "Reduce wasted context.",
            "--guardrail",
            "Preserve checkpoint coverage.",
            "--decision-rule",
            "Accept if context falls without coverage loss.",
            "--corpus",
            "test-novel",
            "--start",
            "1",
            "--end",
            "5",
            "--checkpoint",
            "opening",
            "--model",
            "deepseek:deepseek-v4-flash-low",
            "--toolset",
            "glossary_terms",
            "--toolset",
            "glossary_facts_read",
        ],
    )
    assert created.exit_code == 0, created.output

    updated = runner.invoke(cli.app, ["config", "update", "single-mark-v1", "--replicas", "2", "--max-parallel", "2"])
    assert updated.exit_code == 0, updated.output

    config = load_run_config(workspace, "single-mark-v1", validate_context=True)
    assert config.checkpoints == ["opening"]
    assert [toolset.name for toolset in config.agent.toolsets] == ["glossary_terms", "glossary_facts_read"]
    assert config.execution.replicas == 2


def test_cli_rejects_toolset_not_registered_by_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = workspace_with_corpus_and_checkpoint(tmp_path)
    monkeypatch.setattr(cli, "_workspace", lambda: workspace)
    result = CliRunner().invoke(
        cli.app,
        [
            "config",
            "create",
            "invalid-tools",
            "--change",
            "Test an invalid toolset.",
            "--objective",
            "Exercise validation.",
            "--guardrail",
            "Do not save invalid input.",
            "--decision-rule",
            "Reject.",
            "--corpus",
            "test-novel",
            "--start",
            "1",
            "--end",
            "5",
            "--model",
            "deepseek:deepseek-v4-flash-low",
            "--toolset",
            "missing_toolset",
        ],
    )

    assert result.exit_code == 1
    assert "Unknown agent toolset(s): missing_toolset" in result.output
