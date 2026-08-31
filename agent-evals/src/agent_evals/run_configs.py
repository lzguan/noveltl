import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from src.memory.agent.types import TOOLSET_NAMES

from agent_evals.checkpoints import load_checkpoint
from agent_evals.corpora import inspect_corpus
from agent_evals.schemas import RunConfig
from agent_evals.storage import EvalWorkspace, dump_yaml_model, list_files, load_yaml_model


class RunConfigError(ValueError):
    """A run-config operation could not be completed safely."""


@dataclass(frozen=True)
class RunConfigSummary:
    id: str
    corpus: str
    start_chapter: int
    end_chapter: int
    profile: str
    toolsets: tuple[str, ...]
    replicas: int
    path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "corpus": self.corpus,
            "startChapter": self.start_chapter,
            "endChapter": self.end_chapter,
            "profile": self.profile,
            "toolsets": list(self.toolsets),
            "replicas": self.replicas,
            "path": str(self.path),
        }


def discover_toolset_names() -> tuple[str, ...]:
    """Read available names from the backend's memory-agent metadata."""

    return tuple(TOOLSET_NAMES)


def run_config_path(workspace: EvalWorkspace, config_id: str) -> Path:
    return workspace.run_configs / f"{config_id}.yaml"


def resolve_run_config(workspace: EvalWorkspace, value: str | Path) -> Path:
    candidate = Path(value)
    if candidate.exists():
        return candidate.resolve()
    config_id = str(value)
    matches = [
        path
        for path in (
            workspace.run_configs / f"{config_id}.yaml",
            workspace.run_configs / f"{config_id}.yml",
        )
        if path.is_file()
    ]
    if not matches:
        raise RunConfigError(f"Run config not found: {config_id}")
    if len(matches) > 1:
        raise RunConfigError(f"Run config ID is ambiguous: {config_id}")
    return matches[0].resolve()


def validate_run_config_context(workspace: EvalWorkspace, config: RunConfig) -> None:
    corpus_path = workspace.novels / config.corpus
    if not corpus_path.is_dir():
        raise RunConfigError(f"Corpus not found: {config.corpus}")
    corpus = inspect_corpus(corpus_path, corpus_id=config.corpus)
    chapters = config.chapters
    if chapters.start_inclusive < corpus.first_chapter or chapters.end_inclusive > corpus.last_chapter:
        raise RunConfigError(
            f"Run chapters {chapters.start_inclusive}-{chapters.end_inclusive} are outside "
            f"corpus range {corpus.first_chapter}-{corpus.last_chapter}"
        )

    available = set(discover_toolset_names())
    unknown = sorted(toolset.name for toolset in config.agent.toolsets if toolset.name not in available)
    if unknown:
        raise RunConfigError(f"Unknown agent toolset(s): {', '.join(unknown)}")

    for checkpoint_id in config.checkpoints:
        checkpoint = load_checkpoint(workspace, checkpoint_id, validate_context=True)
        if checkpoint.corpus != config.corpus:
            raise RunConfigError(
                f"Checkpoint {checkpoint.id} uses corpus {checkpoint.corpus}, not {config.corpus}"
            )
        if (
            checkpoint.chapters.start_inclusive < chapters.start_inclusive
            or checkpoint.chapters.end_inclusive > chapters.end_inclusive
        ):
            raise RunConfigError(
                f"Checkpoint {checkpoint.id} chapters "
                f"{checkpoint.chapters.start_inclusive}-{checkpoint.chapters.end_inclusive} "
                f"are outside run range {chapters.start_inclusive}-{chapters.end_inclusive}"
            )


def load_run_config(
    workspace: EvalWorkspace,
    value: str | Path,
    *,
    validate_context: bool = False,
) -> RunConfig:
    config = load_yaml_model(resolve_run_config(workspace, value), RunConfig)
    if validate_context:
        validate_run_config_context(workspace, config)
    return config


def _write_run_config(workspace: EvalWorkspace, config: RunConfig, path: Path) -> None:
    validate_run_config_context(workspace, config)
    workspace.ensure()
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    try:
        dump_yaml_model(temporary, config)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def create_run_config(workspace: EvalWorkspace, config: RunConfig) -> Path:
    path = run_config_path(workspace, config.id)
    if path.exists() or path.with_suffix(".yml").exists():
        raise RunConfigError(f"Run config already exists: {config.id}")
    _write_run_config(workspace, config, path)
    return path


def save_run_config(workspace: EvalWorkspace, config: RunConfig) -> Path:
    path = resolve_run_config(workspace, config.id)
    existing = load_yaml_model(path, RunConfig)
    if existing.id != config.id:
        raise RunConfigError("Run config ID does not match its filename")
    _write_run_config(workspace, config, path)
    return path


def update_run_config(workspace: EvalWorkspace, config_id: str, **changes: Any) -> RunConfig:
    config = load_run_config(workspace, config_id)
    payload = config.model_dump(mode="python")
    payload.update(changes)
    updated = RunConfig.model_validate(payload)
    save_run_config(workspace, updated)
    return updated


def delete_run_config(workspace: EvalWorkspace, config_id: str) -> None:
    resolve_run_config(workspace, config_id).unlink()


def summarize_run_config(path: Path) -> RunConfigSummary:
    config = load_yaml_model(path, RunConfig)
    return RunConfigSummary(
        id=config.id,
        corpus=config.corpus,
        start_chapter=config.chapters.start_inclusive,
        end_chapter=config.chapters.end_inclusive,
        profile=config.agent.profile,
        toolsets=tuple(toolset.name for toolset in config.agent.toolsets),
        replicas=config.execution.replicas,
        path=path.resolve(),
    )


def discover_run_configs(workspace: EvalWorkspace) -> list[RunConfigSummary]:
    workspace.ensure()
    return [summarize_run_config(path) for path in list_files(workspace.run_configs, {".yaml", ".yml"})]


def render_run_config(config: RunConfig, *, as_json: bool) -> str:
    payload = config.model_dump(mode="json", exclude_none=True)
    if as_json:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).rstrip()
