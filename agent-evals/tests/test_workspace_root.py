from pathlib import Path

import pytest

from agent_evals import storage
from agent_evals.storage import EvalWorkspace


@pytest.fixture(autouse=True)
def clear_directory_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_EVAL_CONFIG_DIR", raising=False)
    monkeypatch.delenv("AGENT_EVAL_OUTPUT_DIR", raising=False)


def test_workspace_environment_redirects_data_without_overriding_explicit_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI consumers share configured data, while explicit workspaces remain isolated."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_EVAL_ROOT", "shared-evals")
    workspace = EvalWorkspace()
    assert workspace.root == tmp_path / "shared-evals"
    assert workspace.run_configs == tmp_path / "shared-evals" / "run-configs"
    assert workspace.runs == tmp_path / "shared-evals" / "runs"
    assert EvalWorkspace(tmp_path / "explicit").root == tmp_path / "explicit"


@pytest.mark.parametrize("value", [None, ""])
def test_workspace_preserves_package_default_without_environment_override(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("AGENT_EVAL_ROOT", raising=False)
    else:
        monkeypatch.setenv("AGENT_EVAL_ROOT", value)
    assert EvalWorkspace().root == Path(storage.__file__).resolve().parents[2]


@pytest.mark.parametrize("configs,outputs", [("config", "output"), ("config", ""), ("", "output"), ("", "")])
def test_workspace_overrides_keep_shared_inputs_and_isolate_explicit_workspaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configs: str, outputs: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_EVAL_ROOT", "shared")
    monkeypatch.setenv("AGENT_EVAL_CONFIG_DIR", configs)
    monkeypatch.setenv("AGENT_EVAL_OUTPUT_DIR", outputs)
    workspace = EvalWorkspace()
    shared = tmp_path / "shared"
    output_root = tmp_path / outputs if outputs else shared
    assert workspace.novels == shared / "novels"
    assert workspace.checkpoints == shared / "checkpoints"
    assert workspace.run_configs == (tmp_path / configs if configs else shared / "run-configs")
    assert workspace.runs == output_root / "runs"
    assert workspace.logs == output_root / "logs"
    assert workspace.history == output_root / "history"
    workspace.ensure()
    assert all(path.is_dir() for path in workspace.local_directories())
    explicit = EvalWorkspace(tmp_path / "explicit")
    assert explicit.run_configs == tmp_path / "explicit" / "run-configs"
    assert explicit.runs == tmp_path / "explicit" / "runs"
    assert explicit.logs == tmp_path / "explicit" / "logs"
    assert explicit.history == tmp_path / "explicit" / "history"
