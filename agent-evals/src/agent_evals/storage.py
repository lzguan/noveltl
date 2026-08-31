from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class EvalWorkspace:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path(__file__).resolve().parents[2]).resolve()

    @property
    def novels(self) -> Path:
        return self.root / "novels"

    @property
    def checkpoints(self) -> Path:
        return self.root / "checkpoints"

    @property
    def run_configs(self) -> Path:
        return self.root / "run-configs"

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def history(self) -> Path:
        return self.root / "history"

    def local_directories(self) -> tuple[Path, ...]:
        return (self.novels, self.checkpoints, self.run_configs, self.runs, self.logs, self.history)

    def ensure(self) -> None:
        for directory in self.local_directories():
            directory.mkdir(parents=True, exist_ok=True)


def load_yaml_model[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    with path.open(encoding="utf-8") as stream:
        value: Any = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return model.model_validate(value)


def dump_yaml_model(path: Path, value: BaseModel) -> None:
    payload = value.model_dump(mode="json", exclude_none=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def list_files(directory: Path, suffixes: Iterable[str]) -> list[Path]:
    accepted = set(suffixes)
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in accepted),
        key=lambda path: path.name.casefold(),
    )
