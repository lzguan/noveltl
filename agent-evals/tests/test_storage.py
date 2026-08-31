from pathlib import Path

from agent_evals.storage import EvalWorkspace, list_files


def test_workspace_resolves_all_local_directories_from_explicit_root(tmp_path: Path) -> None:
    workspace = EvalWorkspace(tmp_path)

    workspace.ensure()

    assert workspace.local_directories() == (
        tmp_path / "novels",
        tmp_path / "checkpoints",
        tmp_path / "run-configs",
        tmp_path / "runs",
        tmp_path / "logs",
        tmp_path / "history",
    )
    assert all(path.is_dir() for path in workspace.local_directories())


def test_list_files_filters_and_sorts_authored_yaml(tmp_path: Path) -> None:
    (tmp_path / "zeta.yml").write_text("{}", encoding="utf-8")
    (tmp_path / "Alpha.yaml").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    result = list_files(tmp_path, {".yaml", ".yml"})

    assert [path.name for path in result] == ["Alpha.yaml", "zeta.yml"]
