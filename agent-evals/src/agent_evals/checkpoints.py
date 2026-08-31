import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agent_evals.corpora import inspect_corpus
from agent_evals.schemas import Checkpoint, ExpectedMemory
from agent_evals.storage import EvalWorkspace, dump_yaml_model, list_files, load_yaml_model


class CheckpointError(ValueError):
    """A checkpoint operation could not be completed safely."""


@dataclass(frozen=True)
class CheckpointSummary:
    id: str
    corpus: str
    start_chapter: int
    end_chapter: int
    activity: str
    memory_count: int
    path: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "corpus": self.corpus,
            "startChapter": self.start_chapter,
            "endChapter": self.end_chapter,
            "activity": self.activity,
            "memoryCount": self.memory_count,
            "path": str(self.path),
        }


def checkpoint_path(workspace: EvalWorkspace, checkpoint_id: str) -> Path:
    return workspace.checkpoints / f"{checkpoint_id}.yaml"


def resolve_checkpoint(workspace: EvalWorkspace, value: str | Path) -> Path:
    candidate = Path(value)
    if candidate.exists():
        return candidate.resolve()
    checkpoint_id = str(value)
    matches = [
        path
        for path in (
            workspace.checkpoints / f"{checkpoint_id}.yaml",
            workspace.checkpoints / f"{checkpoint_id}.yml",
        )
        if path.is_file()
    ]
    if not matches:
        raise CheckpointError(f"Checkpoint not found: {checkpoint_id}")
    if len(matches) > 1:
        raise CheckpointError(f"Checkpoint ID is ambiguous: {checkpoint_id}")
    return matches[0].resolve()


def validate_checkpoint_context(workspace: EvalWorkspace, checkpoint: Checkpoint) -> None:
    corpus_path = workspace.novels / checkpoint.corpus
    if not corpus_path.is_dir():
        raise CheckpointError(f"Corpus not found: {checkpoint.corpus}")
    summary = inspect_corpus(corpus_path, corpus_id=checkpoint.corpus)
    chapters = checkpoint.chapters
    if chapters.start_inclusive < summary.first_chapter or chapters.end_inclusive > summary.last_chapter:
        raise CheckpointError(
            f"Checkpoint chapters {chapters.start_inclusive}-{chapters.end_inclusive} are outside "
            f"corpus range {summary.first_chapter}-{summary.last_chapter}"
        )


def load_checkpoint(
    workspace: EvalWorkspace,
    value: str | Path,
    *,
    validate_context: bool = False,
) -> Checkpoint:
    checkpoint = load_yaml_model(resolve_checkpoint(workspace, value), Checkpoint)
    if validate_context:
        validate_checkpoint_context(workspace, checkpoint)
    return checkpoint


def _write_checkpoint(workspace: EvalWorkspace, checkpoint: Checkpoint, path: Path) -> None:
    validate_checkpoint_context(workspace, checkpoint)
    workspace.ensure()
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    try:
        dump_yaml_model(temporary, checkpoint)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def create_checkpoint(workspace: EvalWorkspace, checkpoint: Checkpoint) -> Path:
    path = checkpoint_path(workspace, checkpoint.id)
    if path.exists() or path.with_suffix(".yml").exists():
        raise CheckpointError(f"Checkpoint already exists: {checkpoint.id}")
    _write_checkpoint(workspace, checkpoint, path)
    return path


def save_checkpoint(workspace: EvalWorkspace, checkpoint: Checkpoint) -> Path:
    path = resolve_checkpoint(workspace, checkpoint.id)
    existing = load_yaml_model(path, Checkpoint)
    if existing.id != checkpoint.id:
        raise CheckpointError("Checkpoint ID does not match its filename")
    _write_checkpoint(workspace, checkpoint, path)
    return path


def update_checkpoint(workspace: EvalWorkspace, checkpoint_id: str, **changes: Any) -> Checkpoint:
    checkpoint = load_checkpoint(workspace, checkpoint_id)
    payload = checkpoint.model_dump(mode="python")
    payload.update(changes)
    updated = Checkpoint.model_validate(payload)
    save_checkpoint(workspace, updated)
    return updated


def set_expected_memory(workspace: EvalWorkspace, checkpoint_id: str, memory: ExpectedMemory) -> Checkpoint:
    checkpoint = load_checkpoint(workspace, checkpoint_id)
    memories = list(checkpoint.expected_memories)
    for index, existing in enumerate(memories):
        if existing.id == memory.id:
            memories[index] = memory
            break
    else:
        memories.append(memory)
    return update_checkpoint(workspace, checkpoint_id, expected_memories=memories)


def remove_expected_memory(workspace: EvalWorkspace, checkpoint_id: str, memory_id: str) -> Checkpoint:
    checkpoint = load_checkpoint(workspace, checkpoint_id)
    memories = [memory for memory in checkpoint.expected_memories if memory.id != memory_id]
    if len(memories) == len(checkpoint.expected_memories):
        raise CheckpointError(f"Expected memory not found: {memory_id}")
    return update_checkpoint(workspace, checkpoint_id, expected_memories=memories)


def delete_checkpoint(workspace: EvalWorkspace, checkpoint_id: str) -> None:
    resolve_checkpoint(workspace, checkpoint_id).unlink()


def summarize_checkpoint(path: Path) -> CheckpointSummary:
    checkpoint = load_yaml_model(path, Checkpoint)
    return CheckpointSummary(
        id=checkpoint.id,
        corpus=checkpoint.corpus,
        start_chapter=checkpoint.chapters.start_inclusive,
        end_chapter=checkpoint.chapters.end_inclusive,
        activity=checkpoint.activity,
        memory_count=len(checkpoint.expected_memories),
        path=path.resolve(),
    )


def discover_checkpoints(workspace: EvalWorkspace) -> list[CheckpointSummary]:
    workspace.ensure()
    return [summarize_checkpoint(path) for path in list_files(workspace.checkpoints, {".yaml", ".yml"})]


def render_checkpoint(checkpoint: Checkpoint, *, as_json: bool) -> str:
    payload = checkpoint.model_dump(mode="json", exclude_none=True)
    if as_json:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).rstrip()
