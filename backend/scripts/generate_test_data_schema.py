import argparse
import json
import sys
from pathlib import Path
from typing import Any

from test_support.test_data.formats.v1 import SCHEMA_MODELS

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = BACKEND_ROOT / "tests" / "test_data" / "schema"
META_SCHEMA = "https://json-schema.org/draft/2020-12/schema"


def _render_schema(filename: str, model: type[Any]) -> str:
    schema = model.model_json_schema(by_alias=True, mode="validation")
    schema["$schema"] = META_SCHEMA
    schema["$id"] = filename
    ordered = {
        "$schema": schema.pop("$schema"),
        "$id": schema.pop("$id"),
        **schema,
    }
    return json.dumps(ordered, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def generate(version: int, check: bool) -> bool:
    if version != 1:
        raise ValueError(f"Unsupported test-data schema version: {version}")
    output_dir = SCHEMA_ROOT / f"v{version}" / "json"
    mismatches: list[Path] = []
    for filename, model in sorted(SCHEMA_MODELS.items()):
        path = output_dir / filename
        rendered = _render_schema(filename, model)
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == rendered:
            continue
        mismatches.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
    if mismatches:
        action = "Stale" if check else "Updated"
        for path in mismatches:
            print(f"{action}: {path.relative_to(BACKEND_ROOT)}")
    return not mismatches or not check


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate JSON Schemas for versioned test-data documents.")
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--check", action="store_true", help="Fail if committed schemas differ from generated output.")
    args = parser.parse_args()
    try:
        success = generate(args.version, args.check)
    except ValueError as exc:
        parser.error(str(exc))
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
