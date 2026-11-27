import json
from pathlib import Path

import yaml

from src.main import app


def main() -> None:
    openapi_schema = app.openapi()
    root = Path(__file__).parent.parent

    with (root / "openapi.json").open("w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
        f.write("\n")

    with (root / "openapi.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(openapi_schema, f, sort_keys=False)

    print("OpenAPI JSON and YAML schemas generated successfully.")


if __name__ == "__main__":
    main()
