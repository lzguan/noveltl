import uuid
from datetime import timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.autolabels.models import AutoLabelRun
from test_support.test_data.scenarios import DatabaseScenario


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def test_read_autolabel_runs_and_items(
    client: TestClient,
    xianxia_autolabels_scenario: DatabaseScenario,
) -> None:
    s = xianxia_autolabels_scenario
    novel = s.novels["novel"]
    user = s.users["owner"]
    headers = _auth_headers(user)
    run = s.autolabel_runs["cluener"]
    autolabel = s.autolabels["xianxia-source-chapter-0001"]

    runs_resp = client.get(f"/auto-label-runs?novelId={novel.novel_id}", headers=headers)
    assert runs_resp.status_code == status.HTTP_200_OK
    runs_payload = runs_resp.json()
    assert len(runs_payload) >= 1
    assert runs_payload[0]["modelName"] == "cluener"
    assert runs_payload[0]["modelParams"]["modelName"] == "cluener"
    assert "runId" in runs_payload[0] and "novelId" in runs_payload[0]

    mine_resp = client.get(f"/auto-label-runs?novelId={novel.novel_id}&mine=true", headers=headers)
    assert mine_resp.status_code == status.HTTP_200_OK
    assert all(entry["triggeredBy"] == str(user.user_id) for entry in mine_resp.json())

    item_resp = client.get(f"/auto-labels/{autolabel.auto_label_id}", headers=headers)
    assert item_resp.status_code == status.HTTP_200_OK
    item = item_resp.json()
    assert item["autoLabelId"] == str(autolabel.auto_label_id)
    assert item["runId"] == str(autolabel.run_id)
    assert item["autoLabelStatus"] == "done"
    assert isinstance(item["autoLabelData"], list) and len(item["autoLabelData"]) > 0

    assert client.get(f"/auto-labels/{uuid.uuid4()}", headers=headers).status_code == status.HTTP_404_NOT_FOUND

    by_run_resp = client.get(f"/auto-label-runs/{run.run_id}/auto-labels", headers=headers)
    assert by_run_resp.status_code == status.HTTP_200_OK
    by_run = by_run_resp.json()
    assert len(by_run) == len(s.autolabels)
    assert all(
        entry["autoLabelMeta"]["runId"] == str(run.run_id) and entry["autoLabelMeta"]["autoLabelStatus"] == "done"
        for entry in by_run
    )

    # Chapter numbers are 1-indexed, so start=1, end=2 picks chapter 1 only.
    range_resp = client.get(f"/auto-label-runs/{run.run_id}/auto-labels?start=1&end=2", headers=headers)
    assert range_resp.status_code == status.HTTP_200_OK
    assert len(range_resp.json()) == 1


def test_create_autolabels_and_request_cache(
    client: TestClient,
    xianxia_scenario: DatabaseScenario,
) -> None:
    novel = xianxia_scenario.novels["novel"]
    user = xianxia_scenario.users["owner"]
    chapter_ids = [
        chapter.chapter_id for key, chapter in xianxia_scenario.chapters.items() if key.startswith("novel:")
    ]
    assert len(chapter_ids) > 0

    body = {
        "novelId": str(novel.novel_id),
        "chapterIds": [str(cid) for cid in chapter_ids],
        "params": {"modelName": "cluener"},
    }
    request_key = uuid.uuid4()
    response = client.post(
        f"/auto-labels?requestKey={request_key}",
        json=body,
        headers=_auth_headers(user),
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()

    run = payload["run"]
    assert run["modelName"] == "cluener"
    assert run["novelId"] == str(novel.novel_id)
    assert run["triggeredBy"] == str(user.user_id)
    assert len(payload["autolabels"]) == len(chapter_ids)
    assert all(
        al["autoLabelMeta"]["autoLabelStatus"] == "pending" and al["autoLabelMeta"]["runId"] == run["runId"]
        for al in payload["autolabels"]
    )

    cached_response = client.get(f"/cached/{request_key}")
    assert cached_response.status_code == status.HTTP_200_OK
    cached_payload = cached_response.json()
    assert cached_payload["status"] == "success"
    assert cached_payload["status_code"] == status.HTTP_200_OK
    assert cached_payload["response"] == payload
    assert cached_payload["error"] is None


def test_create_autolabels_scoping_and_permissions(
    client: TestClient,
    test_db: Session,
    novel_permission_scenario: DatabaseScenario,
) -> None:
    s = novel_permission_scenario
    public_novel = s.novels["put"]
    public_chapter = s.chapters["public"]
    run_count_before = test_db.query(AutoLabelRun).count()

    denied = client.post(
        "/auto-labels",
        json={"novelId": str(public_novel.novel_id), "params": {"modelName": "cluener"}},
        headers=_auth_headers(s.users["other"]),
    )
    assert denied.status_code == status.HTTP_404_NOT_FOUND
    assert test_db.query(AutoLabelRun).count() == run_count_before

    scoped = client.post(
        "/auto-labels",
        json={"novelId": str(public_novel.novel_id), "params": {"modelName": "cluener"}},
        headers=_auth_headers(s.users["admin"]),
    )
    assert scoped.status_code == status.HTTP_200_OK
    assert scoped.json()["run"]["novelId"] == str(public_novel.novel_id)
    assert [entry["chapterId"] for entry in scoped.json()["autolabels"]] == [str(public_chapter.chapter_id)]

    viewer_novel = s.novels["ov"]
    viewer_content = s.contents["owner_viewer_v1"]
    viewer_resp = client.post(
        "/auto-labels",
        json={
            "novelId": str(viewer_novel.novel_id),
            "chapterIds": [str(viewer_content.chapter_id)],
            "params": {"modelName": "cluener"},
        },
        headers=_auth_headers(s.users["other"]),
    )
    assert viewer_resp.status_code == status.HTTP_200_OK
    assert [entry["chapterId"] for entry in viewer_resp.json()["autolabels"]] == [str(viewer_content.chapter_id)]
