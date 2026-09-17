from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.translations.router import router
from src.translations.schemas import TranslateStageCreate, TranslationJobCreate


@pytest.fixture
def creation_client(monkeypatch: pytest.MonkeyPatch):
    # The dynamic form relies on HTTP validation before persistence. Replace
    # database/auth seams; their semantics are covered by existing service tests.
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: User()
    with Session() as db:
        app.dependency_overrides[get_db] = lambda: db
        received: list[TranslationJobCreate] = []
        job_id = uuid4()

        def create(db: Session, user: User, request: TranslationJobCreate):
            received.append(request)
            return job_id

        monkeypatch.setattr("src.translations.router.create_translation_job", create)
        with TestClient(app) as client:
            yield client, received, job_id


def test_generic_request_validates_and_applies_defaults(creation_client):
    client, received, job_id = creation_client
    response = client.post(
        "/translation-jobs",
        json={
            "novelId": str(uuid4()),
            "config": {"batchSize": 100},
            "stages": [{"action": "translate", "config": {"model": "qwen-plus"}}],
        },
    )
    assert response.status_code == 201
    assert response.json() == {"jobId": str(job_id)}
    stage = received[0].stages[0]
    assert isinstance(stage, TranslateStageCreate)
    assert stage.config.target_language == "English"


@pytest.mark.parametrize(
    "stages",
    [
        [{"action": "unknown", "config": {}}],
        [{"action": "translate", "config": {}}],
        [{"action": "translate", "config": {"model": "unknown"}}],
        [{"action": "translate", "config": {"model": "qwen-plus", "maxOutputTokens": 0}}],
        [{"action": "translate", "config": {"model": "qwen-plus", "unexpected": True}}],
        [{"action": "prune_memories", "config": {"model": "qwen-plus"}}],
        [{"action": "translate", "config": {"model": "qwen-plus"}}, {"action": "combine_chapter"}],
        [{"action": "translate", "config": []}],
        [],
        [{"action": "translate", "config": {"model": "qwen-plus"}}] * 6,
    ],
)
def test_invalid_stages_do_not_reach_persistence(creation_client, stages):
    client, received, _ = creation_client
    response = client.post(
        "/translation-jobs",
        json={
            "novelId": str(uuid4()),
            "config": {"batchSize": 100},
            "stages": stages,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][0] == "body"
    assert received == []


def test_openapi_exposes_generic_stage_envelope(creation_client):
    client, _, _ = creation_client
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    request = schemas["TranslationJobCreateRequest"]
    assert request["properties"]["stages"]["items"] == {"$ref": "#/components/schemas/TranslationStageRequest"}
    stage = schemas["TranslationStageRequest"]
    assert stage["properties"]["action"]["type"] == "string"
    assert "enum" not in stage["properties"]["action"]
    assert stage["properties"]["config"]["type"] == "object"
    assert stage["properties"]["config"]["additionalProperties"] is True
