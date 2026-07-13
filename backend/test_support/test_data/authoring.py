from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, Protocol

from .domain import AutoLabelArtifact, ContentVersionDataset
from .errors import TestDataError
from .formats.v1 import authoring as v1_authoring
from .formats.v1.documents import AutoLabel, ModelConfigDocument
from .loader import load_catalog, load_config, load_novel

ChapterPrediction = tuple[list[AutoLabel], list[dict[str, Any]]]
Predictor = Callable[[str, object], ChapterPrediction]


class AuthoringFormat(Protocol):
    def add_novel(
        self,
        input_dir: Path,
        catalog_root: Path,
        existing_novel_ids: set[str],
        *,
        no_id: bool,
        dry_run: bool,
    ) -> str: ...

    def validate_config_id(self, config_id: str) -> None: ...

    def write_autolabels(
        self,
        catalog_root: Path,
        novel_id: str,
        config: ModelConfigDocument,
        generated: list[v1_authoring.GeneratedArtifact],
    ) -> None: ...


AUTHORING_FORMATS: dict[int, AuthoringFormat] = {1: v1_authoring}


def _format(schema_version: int) -> AuthoringFormat:
    result = AUTHORING_FORMATS.get(schema_version)
    if result is None:
        raise TestDataError(f"No authoring support for schema version {schema_version}")
    return result


def add_novel(input_dir: Path | str, catalog_root: Path | str, *, no_id: bool = False, dry_run: bool = False) -> str:
    source = Path(input_dir).resolve()
    root = Path(catalog_root).resolve()
    catalog = load_catalog(root)
    return _format(catalog.schema_version).add_novel(
        source,
        root,
        set(catalog.novels),
        no_id=no_id,
        dry_run=dry_run,
    )


def parse_chapters(value: str) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError("Chapter range start exceeds end")
            result.update(range(start, end + 1))
        else:
            result.add(int(part))
    if not result or min(result) < 1:
        raise ValueError("Chapter numbers must be positive")
    return result


def _normalize_cluener_errors(errors: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "word": error["word"],
            "score": float(error["score"]),
            "start": int(error["start"]),
            "end": int(error["end"]),
            "entity_group": error["entity_group"],
        }
        for error in errors
    ]


def _make_default_predictor(config: ModelConfigDocument) -> Predictor:
    from src.autolabels.constants import SepPriority
    from src.autolabels.params import CluenerParams
    from src.autolabels.worker.inference import Cluener

    sep_map = {"high": SepPriority.HIGH, "med": SepPriority.MED, "low": SepPriority.LOW}
    params = CluenerParams(
        chunk_size=config.parameters.chunk_size,
        force_chunk=config.parameters.force_chunk,
        separators={key: sep_map[value] for key, value in config.parameters.separators.items()},
    )
    model = Cluener().model
    if not model.is_deterministic:
        raise TestDataError("Test-data autolabel models must be deterministic")

    def predict(text: str, config_value: object) -> ChapterPrediction:
        labels, errors = model.predict(text, params)
        return (
            [
                AutoLabel(
                    start=label.label_start,
                    end=label.label_end,
                    text=label.label_word,
                    entity_group=label.label_entity_group,
                    score=label.label_score,
                )
                for label in labels
            ],
            _normalize_cluener_errors(errors),
        )

    return predict


def generate_autolabels(
    catalog_root: Path | str,
    novel_id: str,
    config_id: str,
    *,
    chapters: set[int] | None = None,
    version: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    predictor: Predictor | None = None,
) -> int:
    root = Path(catalog_root).resolve()
    catalog = load_catalog(root)
    authoring_format = _format(catalog.schema_version)
    config = load_config(catalog, config_id)
    novel = load_novel(catalog, novel_id)
    authoring_format.validate_config_id(config_id)
    if config.model_name != "cluener":
        raise TestDataError(f"Unsupported autolabel model: {config.model_name}")
    available = {chapter.number for chapter in novel.chapters}
    selected = available if chapters is None else chapters
    missing = selected - available
    if missing:
        raise TestDataError(f"Selected chapters do not exist: {sorted(missing)}")

    targets: list[tuple[ContentVersionDataset, str, AutoLabelArtifact | None]] = []
    for chapter in novel.chapters:
        if chapter.number not in selected:
            continue
        matches = [item for item in chapter.versions if version is None or item.number == version]
        if not matches:
            raise TestDataError(f"Chapter {chapter.number} has no content version {version}")
        content = max(matches, key=lambda item: item.number)
        existing = next((item for item in content.artifacts if item.config_id == config_id), None)
        artifact_id = existing.id if existing else f"{content.id}-autolabels-{config_id}"
        if existing is None or force:
            targets.append((content, artifact_id, existing))
    if dry_run:
        return len(targets)

    predict = predictor or _make_default_predictor(config)
    generated: list[v1_authoring.GeneratedArtifact] = []
    for content, artifact_id, existing in targets:
        prediction = predict(content.text, config)
        for label in prediction[0]:
            if label.start >= label.end or label.end > len(content.text) or content.text[label.start : label.end] != label.text:
                raise TestDataError(f"Generated autolabel {label.text!r} has invalid bounds")
        generated.append((content, artifact_id, existing, prediction))

    authoring_format.write_autolabels(root, novel_id, config, generated)
    return len(generated)
