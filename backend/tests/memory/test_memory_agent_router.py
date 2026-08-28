from datetime import timedelta
from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.memory.exceptions import MemoryAgentEnqueueFailedException
from src.memory.models import MemoryGroup
from test_support.memory import RecordingMemoryAgentDispatcher
from test_support.test_data.scenarios import DatabaseScenario


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _create_group(db: Session, scenario: DatabaseScenario, novel_key: str) -> MemoryGroup:
    group = MemoryGroup(
        memory_group_name=f"{novel_key} memory",
        novel_id=scenario.novels[novel_key].novel_id,
        memory_language="zh",
    )
    db.add(group)
    db.commit()
    return group


def _create_job(client: TestClient, user: User, memory_group_id: UUID):
    return client.post(
        "/memory-agent/jobs",
        headers=_auth_headers(user),
        json={
            "memoryGroupId": str(memory_group_id),
            "startChapterNum": None,
            "endChapterNum": None,
            "params": {"modelName": "deepseek:deepseek-chat", "plugins": []},
        },
    )


def test_memory_agent_router_exposes_authenticated_job_progress_and_dispatch(
    client: TestClient,
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
    recording_memory_agent_dispatcher: RecordingMemoryAgentDispatcher,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "oe")
    editor = novel_permission_scenario.users["other"]
    headers = _auth_headers(editor)

    response = _create_job(client, editor, group.memory_group_id)

    assert response.status_code == status.HTTP_201_CREATED
    job = response.json()
    memory_job_id = UUID(job["memoryJobId"])
    assert job["memoryGroupId"] == str(group.memory_group_id)
    assert job["jobParams"] == {"modelName": "deepseek:deepseek-chat", "plugins": []}
    assert client.get(f"/memory-agent/jobs/{memory_job_id}").status_code == status.HTTP_401_UNAUTHORIZED

    jobs_response = client.get(
        "/memory-agent/jobs",
        params={"memoryGroupId": str(group.memory_group_id)},
        headers=headers,
    )
    assert jobs_response.status_code == status.HTTP_200_OK
    assert [item["memoryJobId"] for item in jobs_response.json()] == [str(memory_job_id)]

    summaries_response = client.get(
        "/memory-agent/job-summaries",
        params={"memoryGroupId": str(group.memory_group_id)},
        headers=headers,
    )
    assert summaries_response.status_code == status.HTTP_200_OK
    assert summaries_response.json() == [
        {
            "job": job,
            "taskCounts": {
                "pending": 1,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            },
        }
    ]
    summary_response = client.get(
        f"/memory-agent/job-summaries/{memory_job_id}",
        headers=headers,
    )
    assert summary_response.status_code == status.HTTP_200_OK
    assert summary_response.json() == summaries_response.json()[0]

    tasks_response = client.get(f"/memory-agent/jobs/{memory_job_id}/tasks", headers=headers)
    assert tasks_response.status_code == status.HTTP_200_OK
    task_page = tasks_response.json()
    assert task_page["count"] == 1
    assert task_page["rows"][0]["taskStatus"] == "pending"
    chapter_id = UUID(task_page["rows"][0]["chapterId"])

    assert (
        client.post(f"/memory-agent/jobs/{memory_job_id}/start", headers=headers).status_code
        == status.HTTP_202_ACCEPTED
    )
    assert (
        client.post(
            f"/memory-agent/jobs/{memory_job_id}/tasks/{chapter_id}/start",
            headers=headers,
        ).status_code
        == status.HTTP_202_ACCEPTED
    )
    assert recording_memory_agent_dispatcher.jobs == [memory_job_id]
    assert recording_memory_agent_dispatcher.tasks == [(memory_job_id, chapter_id)]


def test_memory_agent_router_maps_access_state_and_publication_failures(
    client: TestClient,
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
    recording_memory_agent_dispatcher: RecordingMemoryAgentDispatcher,
) -> None:
    group = _create_group(test_db, novel_permission_scenario, "ov")
    owner = novel_permission_scenario.users["owner"]
    viewer = novel_permission_scenario.users["other"]

    assert _create_job(client, viewer, group.memory_group_id).status_code == status.HTTP_404_NOT_FOUND
    created = _create_job(client, owner, group.memory_group_id)
    assert created.status_code == status.HTTP_201_CREATED
    memory_job_id = UUID(created.json()["memoryJobId"])
    task_page = client.get(
        f"/memory-agent/jobs/{memory_job_id}/tasks",
        headers=_auth_headers(owner),
    ).json()
    chapter_id = UUID(task_page["rows"][0]["chapterId"])

    retry_response = client.post(
        f"/memory-agent/jobs/{memory_job_id}/tasks/{chapter_id}/retry",
        headers=_auth_headers(owner),
    )
    assert retry_response.status_code == status.HTTP_409_CONFLICT

    recording_memory_agent_dispatcher.enqueue_error = MemoryAgentEnqueueFailedException("broker unavailable")
    start_response = client.post(
        f"/memory-agent/jobs/{memory_job_id}/start",
        headers=_auth_headers(owner),
    )
    assert start_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert start_response.json() == {"detail": "broker unavailable"}
