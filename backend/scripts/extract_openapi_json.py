import json
from pathlib import Path

from src.main import app  # Import your FastAPI instance


def generate_openapi_json():
    # Use the app's internal openapi method to get the schema
    openapi_schema = app.openapi()

    with open(Path(__file__).parent.parent / "openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)


if __name__ == "__main__":
    generate_openapi_json()
