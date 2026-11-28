import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
OPENAPI_PATH = REPO_ROOT / "reader-api" / "openapi.json"
OUTPUT_PATH = BACKEND_DIR / "src" / "publishing" / "reader_schemas.py"
DATAMODEL_CODEGEN_VERSION = "0.104.0"


def _collect_refs(node: Any, out: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            out.add(ref.removeprefix("#/components/schemas/"))
        for value in node.values():
            _collect_refs(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_refs(item, out)


def _filter_ingest_spec(spec: dict[str, Any]) -> dict[str, Any]:
    ingest_paths: dict[str, Any] = {}
    referenced: set[str] = set()

    for path, path_item in spec.get("paths", {}).items():
        if not path.startswith("/ingest"):
            continue
        filtered_item: dict[str, Any] = {}
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                filtered_item[method] = operation
                continue
            filtered_op = dict(operation)
            responses = operation.get("responses", {})
            filtered_op["responses"] = {
                code: body for code, body in responses.items() if str(code).startswith("2")
            }
            filtered_item[method] = filtered_op
            _collect_refs(filtered_op, referenced)
        ingest_paths[path] = filtered_item

    all_schemas: dict[str, Any] = spec.get("components", {}).get("schemas", {})
    included_schemas: dict[str, Any] = {}
    pending = list(referenced)
    while pending:
        name = pending.pop()
        if name in included_schemas or name not in all_schemas:
            continue
        schema = all_schemas[name]
        included_schemas[name] = schema
        nested: set[str] = set()
        _collect_refs(schema, nested)
        pending.extend(nested - included_schemas.keys())

    return {
        "openapi": spec.get("openapi", "3.1.0"),
        "info": spec.get("info", {"title": "Reader Ingest", "version": "1.0.0"}),
        "paths": ingest_paths,
        "components": {"schemas": dict(sorted(included_schemas.items()))},
    }


def main() -> None:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    filtered = _filter_ingest_spec(spec)

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as tmp:
        json.dump(filtered, tmp, indent=2)
        tmp.flush()

        subprocess.run(
            [
                "uvx",
                "--from",
                f"datamodel-code-generator=={DATAMODEL_CODEGEN_VERSION}",
                "datamodel-codegen",
                "--input",
                tmp.name,
                "--input-file-type",
                "openapi",
                "--output",
                str(OUTPUT_PATH),
                "--output-model-type",
                "pydantic_v2.BaseModel",
                "--target-python-version",
                "3.13",
                "--use-annotated",
                "--snake-case-field",
                "--use-standard-collections",
                "--use-union-operator",
                "--collapse-root-models",
                "--collapse-constrained-root-models-as-annotated",
                "--strict-nullable",
                "--allow-population-by-field-name",
                "--formatters",
                "builtin",
                "--disable-timestamp",
                "--custom-file-header",
                "# Generated from reader-api/openapi.json (/ingest/*) by backend/scripts/generate_reader_schemas.py. Do not edit manually.",
            ],
            check=True,
        )

    subprocess.run(["uv", "--directory", str(BACKEND_DIR), "run", "--no-sync", "ruff", "check", "--fix", str(OUTPUT_PATH)], check=True)
    subprocess.run(["uv", "--directory", str(BACKEND_DIR), "run", "--no-sync", "ruff", "format", str(OUTPUT_PATH)], check=True)
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
