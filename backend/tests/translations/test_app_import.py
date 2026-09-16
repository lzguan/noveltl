import os
import subprocess
import sys
from pathlib import Path


def test_api_import_does_not_load_qwen_dependencies() -> None:
    # Uvicorn must boot without loading worker-only provider settings or SDK
    # adapters. A fresh interpreter avoids pytest's already-imported app masking
    # an import-time dependency; the guard also excludes dotenv interference.
    script = """
import importlib.abc
import sys

class WorkerImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"src.translations.settings", "src.translations.clients.qwen_client"}:
            raise AssertionError(f"API imported worker dependency: {fullname}")

sys.meta_path.insert(0, WorkerImportGuard())
from src.main import app
assert app is not None
"""
    env = {key: value for key, value in os.environ.items() if key not in {"QWEN_API_KEY", "QWEN_API_URL"}}
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
