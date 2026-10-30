from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.utils import create_access_token
from src.translations.celery_app import app
from src.translations.models import TranslationBatch, TranslationJob, TranslationStage, TranslationTask
from src.translations.service import TranslationNotFoundError
from src.translations.types import TranslationTaskStatus as State
from src.translations.viewer import list_translation_jobs, read_translation_batches
from test_support.test_data.scenarios import DatabaseScenario


def seed_job(db: Session, novel_id: UUID) -> tuple[TranslationJob, list[list[TranslationTask]]]:
    job = TranslationJob(novel_id=novel_id, config={"batch_size": 1})
    db.add(job)
    db.flush()
    stages = [
        TranslationStage(job_id=job.job_id, stage_num=n, action="translate", config={"model": "qwen-plus"})
        for n in range(2)
    ]
    batches = [TranslationBatch(job_id=job.job_id, batch_num=n) for n in range(6)]
    db.add_all([*stages, *batches])
    db.flush()
    tasks = [
        [
            TranslationTask(
                stage_id=stage.stage_id,
                batch_id=batch.batch_id,
                status=State.READY if stage.stage_num == 0 else State.WAITING,
            )
            for stage in stages
        ]
        for batch in batches
    ]
    db.add_all([task for batch in tasks for task in batch])
    db.commit()
    return job, tasks


# The viewer needs authorized, bounded snapshots with SQL counts matching task
# states, including mixed failures and live/expired leases. Keep PostgreSQL real.
def test_viewer_counts_pagination_and_access(test_db: Session, sample_scenario: DatabaseScenario) -> None:
    user = sample_scenario.users["admin"]
    novel_id = sample_scenario.novels["novel_1"].novel_id
    job, tasks = seed_job(test_db, novel_id)
    now = test_db.execute(select(func.now())).scalar_one()
    for task in tasks[0]:
        task.status = State.COMPLETE
    tasks[1][0].status = State.PROCESSING
    tasks[1][0].claim_token = uuid4()
    tasks[1][0].claim_expires_at = now + timedelta(minutes=5)
    tasks[2][0].failed_at, tasks[2][0].error = now, "Provider failure"
    for task in tasks[3]:
        task.failed_at, task.error = now, "Cancelled by user"
    tasks[5][0].status = State.PREPARING
    tasks[5][0].claim_token = uuid4()
    tasks[5][0].claim_expires_at = now - timedelta(minutes=1)
    test_db.commit()
    other, _ = seed_job(test_db, novel_id)
    foreign, _ = seed_job(test_db, sample_scenario.novels["novel_2"].novel_id)
    page = list_translation_jobs(test_db, user, novel_id, offset=0, limit=1)
    second = list_translation_jobs(test_db, user, novel_id, offset=1, limit=1)
    assert page.total == second.total == 2
    assert {page.items[0].job_id, second.items[0].job_id} == {job.job_id, other.job_id}
    assert foreign.job_id not in {page.items[0].job_id, second.items[0].job_id}
    detail = read_translation_batches(test_db, user, job.job_id, offset=0, limit=5)
    assert detail.total == 6 and len(detail.items) == 5
    assert [batch.batch_num for batch in detail.items] == list(range(5))
    assert all(len(batch.tasks) == 2 for batch in detail.items)
    assert detail.job.progress.model_dump() == dict(
        total_tasks=12,
        completed_tasks=2,
        total_batches=6,
        completed_batches=1,
        active_batches=1,
        failed_batches=1,
        cancelled_batches=1,
        startable_batches=1,
        resumable_batches=2,
        retryable_batches=4,
    )
    last = read_translation_batches(test_db, user, job.job_id, offset=5, limit=5)
    assert [batch.batch_num for batch in last.items] == [5]
    assert last.job.progress == detail.job.progress
    assert list_translation_jobs(test_db, user, novel_id, offset=20, limit=5).items == []
    for read in (
        lambda: list_translation_jobs(test_db, sample_scenario.users["user"], novel_id, offset=0, limit=5),
        lambda: read_translation_batches(test_db, sample_scenario.users["user"], job.job_id, offset=0, limit=5),
    ):
        with pytest.raises(TranslationNotFoundError):
            read()


def test_viewer_routes_and_batch_control_scope(
    client: TestClient, test_db: Session, sample_scenario: DatabaseScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = sample_scenario.users["admin"]
    novel_id = sample_scenario.novels["novel_1"].novel_id
    job, tasks = seed_job(test_db, novel_id)
    foreign, foreign_tasks = seed_job(test_db, novel_id)
    headers = {"Authorization": "Bearer " + create_access_token({"sub": user.user_name}, timedelta(minutes=5))}
    url = f"/translation-jobs/{job.job_id}/batches"
    assert client.get(url).status_code == 401
    assert (
        client.get("/translation-jobs", params={"novelId": str(novel_id), "limit": 51}, headers=headers).status_code
        == 422
    )
    response = client.get("/translation-jobs", params={"novelId": str(novel_id), "limit": 1}, headers=headers)
    assert response.status_code == 200 and response.json()["total"] == 2
    response = client.get(url, params={"offset": 5}, headers=headers)
    assert response.status_code == 200 and len(response.json()["items"]) == 1
    assert "claimToken" not in response.json()["items"][0]["tasks"][0]
    dispatched = []
    monkeypatch.setattr(
        app.tasks["src.translations.actions.translate.prepare"], "apply_async", lambda args: dispatched.append(args[0])
    )
    for operation in ("start", "resume"):
        result = client.post(f"{url}/{tasks[2][0].batch_id}/{operation}", headers=headers)
        assert result.status_code == 200
        assert result.json()["dispatchedTaskIds"] == [str(tasks[2][0].task_id)]
        assert result.json()["affectedBatchIds"] == [str(tasks[2][0].batch_id)]
        assert client.post(f"{url}/{foreign_tasks[0][0].batch_id}/{operation}", headers=headers).status_code == 404
    assert dispatched == [tasks[2][0].task_id] * 2
