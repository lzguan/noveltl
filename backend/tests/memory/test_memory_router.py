from datetime import timedelta
from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.main import app
from src.memory.models import MemoryGroup
from test_support.test_data.scenarios import DatabaseScenario


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _create_memory_group(
    client: TestClient,
    user: User,
    novel_id: UUID,
    *,
    language: str = "zh",
):
    return client.post(
        "/memory-groups",
        json={
            "memoryGroupName": "Main memory",
            "novelId": str(novel_id),
            "memoryLanguage": language,
        },
        headers=_auth_headers(user),
    )


def test_editor_can_create_memory_group(
    client: TestClient,
    test_db: Session,
    novel_access_scenario: DatabaseScenario,
) -> None:
    novel = novel_access_scenario.novels["oe"]

    response = _create_memory_group(client, novel_access_scenario.users["other"], novel.novel_id)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload == {
        "memoryGroupId": payload["memoryGroupId"],
        "memoryGroupName": "Main memory",
        "novelId": str(novel.novel_id),
        "memoryLanguage": "zh",
    }
    memory_group = test_db.scalar(
        select(MemoryGroup).where(MemoryGroup.memory_group_id == UUID(payload["memoryGroupId"]))
    )
    assert memory_group is not None
    assert memory_group.memory_group_name == "Main memory"


def test_viewer_cannot_create_memory_group(
    client: TestClient,
    test_db: Session,
    novel_access_scenario: DatabaseScenario,
) -> None:
    novel = novel_access_scenario.novels["ov"]

    response = _create_memory_group(client, novel_access_scenario.users["other"], novel.novel_id)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert test_db.scalars(select(MemoryGroup).where(MemoryGroup.novel_id == novel.novel_id)).all() == []


def test_unknown_memory_language_returns_not_found(
    client: TestClient,
    test_db: Session,
    novel_access_scenario: DatabaseScenario,
) -> None:
    novel = novel_access_scenario.novels["oe"]

    response = _create_memory_group(
        client,
        novel_access_scenario.users["other"],
        novel.novel_id,
        language="xx",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert test_db.scalars(select(MemoryGroup).where(MemoryGroup.novel_id == novel.novel_id)).all() == []


def test_memory_routes_are_exposed_in_openapi() -> None:
    openapi = app.openapi()
    paths = openapi["paths"]

    assert set(paths["/memories/{memoryId}"]) == {"get", "delete"}
    assert set(paths["/memory-groups/{memoryGroupId}/glossary/memories"]) == {"get", "post"}
    assert set(paths["/memory-groups/{memoryGroupId}/glossary/terms"]) == {"get", "post"}
    assert set(paths["/memory-groups/{memoryGroupId}/glossary/terms/{termId}"]) == {"patch", "delete"}


def test_memory_delete_contract_has_no_response_body() -> None:
    operation = app.openapi()["paths"]["/memories/{memoryId}"]["delete"]

    assert set(operation["responses"]) == {"204", "404", "422"}
    assert "content" not in operation["responses"]["204"]


def test_memories_for_term_contract_supports_chapter_scope() -> None:
    operation = app.openapi()["paths"]["/memory-groups/{memoryGroupId}/glossary/terms/{termId}/memories"]["get"]

    query_parameters = {parameter["name"] for parameter in operation["parameters"] if parameter["in"] == "query"}
    assert query_parameters == {"skip", "limit", "chapterId"}
