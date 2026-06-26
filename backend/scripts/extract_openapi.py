from pathlib import Path

from src.main import app  # Import your FastAPI instance

openapi_schema = app.openapi()


def generate_openapi_json():
    import json
    # Use the app's internal openapi method to get the schema

    with open(Path(__file__).parent.parent / "openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    print("OpenAPI JSON schema generated successfully.")


def generate_openapi_yaml():
    import yaml

    with open(Path(__file__).parent.parent / "openapi.yaml", "w") as f:
        yaml.dump(openapi_schema, f, indent=2)
    print("OpenAPI YAML schema generated successfully.")


if __name__ == "__main__":
    generate_openapi_json()
    generate_openapi_yaml()
