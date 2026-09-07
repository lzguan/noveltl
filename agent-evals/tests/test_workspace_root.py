from pathlib import Path

import pytest

from agent_evals import storage
from agent_evals.storage import EvalWorkspace


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
