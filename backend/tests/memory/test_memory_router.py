from datetime import timedelta
from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
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


def test_create_memory_group_access_and_validation(
    client: TestClient,
    test_db: Session,
    novel_access_scenario: DatabaseScenario,
) -> None:
    user = novel_access_scenario.users["other"]
    viewer_novel = novel_access_scenario.novels["ov"]
    editor_novel = novel_access_scenario.novels["oe"]

    viewer_response = _create_memory_group(client, user, viewer_novel.novel_id)
    assert viewer_response.status_code == status.HTTP_404_NOT_FOUND
    assert test_db.scalars(select(MemoryGroup).where(MemoryGroup.novel_id == viewer_novel.novel_id)).all() == []

    bad_lang_response = _create_memory_group(client, user, editor_novel.novel_id, language="xx")
    assert bad_lang_response.status_code == status.HTTP_404_NOT_FOUND
    assert test_db.scalars(select(MemoryGroup).where(MemoryGroup.novel_id == editor_novel.novel_id)).all() == []

    response = _create_memory_group(client, user, editor_novel.novel_id)
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload == {
        "memoryGroupId": payload["memoryGroupId"],
        "memoryGroupName": "Main memory",
        "novelId": str(editor_novel.novel_id),
        "memoryLanguage": "zh",
    }
    memory_group = test_db.scalar(
        select(MemoryGroup).where(MemoryGroup.memory_group_id == UUID(payload["memoryGroupId"]))
    )
    assert memory_group is not None
    assert memory_group.memory_group_name == "Main memory"
