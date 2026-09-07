import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import agent_evals


@pytest.mark.parametrize("local_file", [False, True])
def test_startup_loads_only_runner_dotenv_and_preserves_process_environment(
    tmp_path: Path, local_file: bool
) -> None:
    """Runner consumers see local file settings without losing container configuration."""
    project = tmp_path / "runner"
    package = project / "src" / "agent_evals"
    package.mkdir(parents=True)
    assert agent_evals.__file__ is not None
    shutil.copyfile(agent_evals.__file__, package / "__init__.py")
    (tmp_path / ".env").write_text("AGENT_EVAL_ROOT=wrong-parent\n", encoding="utf-8")
    if local_file:
        (project / ".env").write_text(
            "AGENT_EVAL_ROOT=local-data\nNOVELTL_DOTENV_TEST_EXISTING=file-value\n",
            encoding="utf-8",
        )
    env = os.environ.copy()
    env.pop("AGENT_EVAL_ROOT", None)
    env.pop("PYTHON_DOTENV_DISABLED", None)
    env["PYTHONPATH"] = str(project / "src")
    env["NOVELTL_DOTENV_TEST_EXISTING"] = "container-value"
    expected = "local-data" if local_file else None
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import agent_evals, os; "
            f"assert os.getenv('AGENT_EVAL_ROOT') == {expected!r}; "
            "assert os.environ['NOVELTL_DOTENV_TEST_EXISTING'] == 'container-value'",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
