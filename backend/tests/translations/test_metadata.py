from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.translations.router import router
from src.translations.schemas import PruneMemoriesConfig, TranslateConfig, TranslateStageCreate, TranslationJobCreate


def test_action_metadata_supports_pipeline_builder() -> None:
    # The builder relies on schemas matching creation, and on the static route
    # winning over /{jobId}. Authentication is replaced: user lookup is unrelated
    # to this metadata contract and would otherwise require a database.
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: User()
    with TestClient(app) as client:
        response = client.get("/translation-jobs/actions")
    assert response.status_code == 200
    actions = {action["name"]: action for action in response.json()["actions"]}
    # The loader is inserted by job creation and is not offered to the builder.
    configs = {"translate": TranslateConfig, "prune_memories": PruneMemoriesConfig}
    assert actions.keys() == configs.keys()
    for name, config in configs.items():
        action = actions[name]
        assert set(action["inputTypes"]) == config.SIGNATURE.input_types
        assert set(action["outputTypes"]) == config.SIGNATURE.output_types
        assert action["label"]
        assert action["allowedAsFirstStage"] is True
        assert action["configSchema"]["type"] == "object"

    schema = actions["translate"]["configSchema"]
    assert schema["required"] == ["model"]
    assert schema["additionalProperties"] is False
    properties = schema["properties"]
    assert properties["targetLanguage"]["default"] == "English"
    assert properties["targetLanguage"]["minLength"] == 1
    assert properties["maxOutputTokens"]["anyOf"][0]["exclusiveMinimum"] == 0
    assert properties["maxOutputTokens"]["title"] == "Max output tokens"
    assert properties["maxOutputTokens"]["x-ui"] == {
        "control": "number",
        "showAfter": "model",
        "placeholder": "Provider default",
    }
    assert properties["instructions"]["x-ui"] == {"control": "textarea", "showAfter": "model"}
    model_ref = properties["model"]["$ref"]
    assert model_ref.startswith("#/$defs/")
    for model in schema["$defs"][model_ref.removeprefix("#/$defs/")]["enum"]:
        request = TranslationJobCreate.model_validate(
            {
                "novelId": str(uuid4()),
                "config": {"batchSize": 100},
                "stages": [{"action": "translate", "config": {"model": model}}],
            }
        )
        assert isinstance(request.stages[0], TranslateStageCreate)
        assert request.stages[0].config.target_language == "English"

    # Input streams are configured once for the job, not on the stages that read them.
    for name in configs:
        assert (
            not {"memoryGroupId", "pluginNames", "memoryTypes", "excludeCurrentChapter"}
            & actions[name]["configSchema"]["properties"].keys()
        )


def test_action_metadata_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/translation-jobs/actions").status_code == 401
