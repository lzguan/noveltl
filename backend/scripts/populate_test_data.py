"""
Populate test data by running deterministic autolabeling models on chapter .txt files.

Reads plaintext chapters from `chapters/`, runs NER models configured in
`testconfig.json`, and writes label outputs as `.json` files under `autolabels/`
mirroring the directory tree.

Compares `testconfig.json` against `testconfig.lock.json` to detect config changes.
A config change triggers full regeneration; otherwise the script skips
existing outputs (incremental mode).

Sanity checks:
  1. Warns about leaf folders in `chapters/` with no .txt files.
  2. Warns when a model produces zero labels for a chapter.
"""

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_TEST_DATA = Path(__file__).resolve().parents[1] / "tests" / "test_data"
CHAPTERS_DIR = _TEST_DATA / "chapters"
AUTOLAB_DIR = _TEST_DATA / "autolabels"
TESTCONFIG = _TEST_DATA / "testconfig.json"
TESTCONFIG_LOCK = _TEST_DATA / "testconfig.lock.json"

# ── Lazy model loaders (deferred imports so --dry-run doesn't need HF) ──────


def _load_cluener():
    from src.autolabels.worker.inference import Cluener

    return Cluener().model


MODEL_LOADERS: dict[str, Callable[[], Any]] = {
    "cluener": _load_cluener,
}

# ── Params validation per model (applies defaults) ──────────────────────────


def _resolve_params(model_name: str, config: dict[str, Any]) -> Any:
    if model_name == "cluener":
        from src.autolabels.constants import SepPriority
        from src.autolabels.schemas import CluenerModelParams

        sep_map = {"high": SepPriority.HIGH, "med": SepPriority.MED, "low": SepPriority.LOW}
        processed = dict(config)
        processed["separators"] = {str(k): sep_map[str(v).lower()] for k, v in config.get("separators", {}).items()}
        return CluenerModelParams.model_validate(processed)
    raise KeyError(f"No params class registered for model '{model_name}'")


# ── CLI ─────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Populate autolabel test data from chapters/")
    p.add_argument("--model", type=str, choices=sorted(MODEL_LOADERS), help="Run only this model")
    p.add_argument("--force", action="store_true", help="Regenerate all outputs (bypass incremental and config prompt)")
    p.add_argument("-y", "--yes", action="store_true", help="Skip the config-change confirmation prompt")
    p.add_argument("--dry-run", action="store_true", help="Check state and print plan, never load models")
    p.add_argument("--verbose", action="store_true", help="Print per-file progress")
    return p.parse_args()


# ── Entry point ─────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()

    if not TESTCONFIG.exists():
        print(f"ERROR: {TESTCONFIG} not found. Create it first.", file=sys.stderr)
        sys.exit(1)

    config = json.loads(TESTCONFIG.read_text(encoding="utf-8"))
    mode = _check_config_state(config)
    models_to_run = _resolve_models(config, args.model, args.verbose)

    if args.dry_run:
        _do_dry_run(config, mode, models_to_run, args)
        return

    if mode == "full" and not args.yes and not args.force:
        answer = input("testconfig.json changed since last run. Regenerate all outputs? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return

    _check_empty_leaf_folders()

    file_count = 0
    warn_count = 0

    for model_name in models_to_run:
        model_config = config["models"][model_name]
        model = MODEL_LOADERS[model_name]()
        if not model.is_deterministic:
            print(f"SKIP {model_name}: not deterministic")
            continue

        params = _resolve_params(model_name, model_config)

        for txt_path in sorted(CHAPTERS_DIR.rglob("*.txt")):
            rel = txt_path.relative_to(CHAPTERS_DIR)
            out_dir = AUTOLAB_DIR / rel.parent / model_name
            out_file = out_dir / f"{txt_path.stem}.json"

            if mode == "incremental" and not args.force and out_file.exists():
                if args.verbose:
                    print(f"SKIP {rel} ({model_name})")
                continue

            text = txt_path.read_text(encoding="utf-8")
            if args.verbose:
                print(f"RUN  {rel} ({model_name})")

            labels, errors = model.predict(text, params)
            file_count += 1

            if not labels:
                print(f"WARNING: {rel} ({model_name}) produced zero labels")
                warn_count += 1

            out_dir.mkdir(parents=True, exist_ok=True)
            out_file.write_text(
                json.dumps(
                    {
                        "auto_label_data": [lab.model_dump() for lab in labels],
                        "auto_label_model_name": model_name,
                        "auto_label_model_params": params.model_dump(),
                        "auto_label_status": "done",
                        "auto_label_message": str(errors),
                        "auto_label_last_job_id": None,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    # Snapshot config on success
    TESTCONFIG_LOCK.write_text(json.dumps(config, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    summary = f"Generated {file_count} file(s)."
    if warn_count:
        summary += f" {warn_count} warning(s) (see above)."
    print(summary)


# ── Dry run ─────────────────────────────────────────────────────────────────


def _do_dry_run(config: dict[str, Any], mode: str, models: list[str], args: argparse.Namespace) -> None:
    print(f"Config state: {mode}")
    print(f"Models: {', '.join(sorted(models))}")
    print()

    would_run = 0
    would_skip = 0

    for txt_path in sorted(CHAPTERS_DIR.rglob("*.txt")):
        for model_name in sorted(models):
            rel = txt_path.relative_to(CHAPTERS_DIR)
            out_file = AUTOLAB_DIR / rel.parent / model_name / f"{txt_path.stem}.json"

            if mode == "incremental" and not args.force and out_file.exists():
                would_skip += 1
                if args.verbose:
                    print(f"SKIP {rel} ({model_name})")
            else:
                would_run += 1
                if args.verbose:
                    print(f"WOULD {rel} ({model_name})")

    if would_run == 0:
        print(f"All {would_skip} output(s) up to date.")
    else:
        print(f"Would (re)generate {would_run} file(s), skip {would_skip}.")


# ── Config state ────────────────────────────────────────────────────────────


def _check_config_state(config: dict[str, Any]) -> str:
    """Compare testconfig.json with testconfig.lock.json. Returns 'full' or 'incremental'."""
    if not TESTCONFIG_LOCK.exists():
        return "full"
    try:
        runtime = json.loads(TESTCONFIG_LOCK.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "full"
    if json.dumps(config, sort_keys=True) != json.dumps(runtime, sort_keys=True):
        print("testconfig.json changed since last run → full regeneration")
        return "full"
    return "incremental"


# ── Model resolution ────────────────────────────────────────────────────────


def _resolve_models(config: dict[str, Any], model_filter: str | None, verbose: bool) -> list[str]:
    """Return sorted list of model names to run, filtered by --model flag."""
    configured = set(config.get("models", {}))
    loadable = set(MODEL_LOADERS)

    for name in configured - loadable:
        print(f"WARNING: model '{name}' in testconfig.json has no registered loader, skipping")

    if model_filter and model_filter not in configured:
        print(f"ERROR: model '{model_filter}' not found in testconfig.json", file=sys.stderr)
        sys.exit(1)

    models = sorted(configured & loadable)
    if model_filter:
        models = [model_filter]

    if verbose:
        print(f"Models to run: {', '.join(models)}")
    return models


# ── Sanity checks ───────────────────────────────────────────────────────────


def _check_empty_leaf_folders() -> None:
    """Warn about directories under chapters/ that are leaves with no .txt files."""
    for dir_path in sorted(CHAPTERS_DIR.rglob("*")):
        if not dir_path.is_dir():
            continue
        if [d for d in dir_path.iterdir() if d.is_dir()]:
            continue  # has subdirectories, not a leaf
        txt_files = list(dir_path.glob("*.txt"))
        if not txt_files:
            print(f"WARNING: leaf folder with no .txt files: {dir_path.relative_to(_TEST_DATA)}")


if __name__ == "__main__":
    main()
