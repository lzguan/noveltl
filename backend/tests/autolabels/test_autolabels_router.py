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


class TestAutoLabelRunsRouter:
    def test_list_runs(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: DatabaseScenario,
    ) -> None:
        novel = xianxia_autolabels_scenario.novels["novel"]
        user = xianxia_autolabels_scenario.users["owner"]

        response = client.get(
            f"/auto-label-runs?novelId={novel.novel_id}",
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert isinstance(payload, list)
        assert len(payload) >= 1
        assert payload[0]["modelName"] == "cluener"
        assert "runId" in payload[0]
        assert "novelId" in payload[0]
        assert "modelParams" in payload[0]
        assert payload[0]["modelParams"]["modelName"] == "cluener"

    def test_list_runs_mine(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: DatabaseScenario,
    ) -> None:
        novel = xianxia_autolabels_scenario.novels["novel"]
        user = xianxia_autolabels_scenario.users["owner"]

        response = client.get(
            f"/auto-label-runs?novelId={novel.novel_id}&mine=true",
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        for run in payload:
            assert run["triggeredBy"] == str(user.user_id)


class TestAutoLabelRouter:
    def test_get_autolabel_by_id(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: DatabaseScenario,
    ) -> None:
        xianxia_autolabels_scenario.novels["novel"]
        user = xianxia_autolabels_scenario.users["owner"]
        autolabel = xianxia_autolabels_scenario.autolabels["xianxia-source-chapter-0001"]

        response = client.get(
            f"/auto-labels/{autolabel.auto_label_id}",
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["autoLabelId"] == str(autolabel.auto_label_id)
        assert payload["runId"] == str(autolabel.run_id)
        assert payload["autoLabelStatus"] == "done"
        assert payload["autoLabelData"] is not None
        assert isinstance(payload["autoLabelData"], list)
        assert len(payload["autoLabelData"]) > 0

    def test_get_autolabel_by_id_not_found(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: DatabaseScenario,
    ) -> None:
        xianxia_autolabels_scenario.novels["novel"]
        user = xianxia_autolabels_scenario.users["owner"]
        fake_id = uuid.uuid4()

        response = client.get(
            f"/auto-labels/{fake_id}",
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAutoLabelsByRunRouter:
    def test_get_autolabels_by_run(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: DatabaseScenario,
    ) -> None:
        xianxia_autolabels_scenario.novels["novel"]
        user = xianxia_autolabels_scenario.users["owner"]
        run = xianxia_autolabels_scenario.autolabel_runs["cluener"]
        expected_count = len(xianxia_autolabels_scenario.autolabels)

        response = client.get(
            f"/auto-label-runs/{run.run_id}/auto-labels",
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert len(payload) == expected_count
        for entry in payload:
            assert entry["autoLabelMeta"]["runId"] == str(run.run_id)
            assert entry["autoLabelMeta"]["autoLabelStatus"] in ("done",)

    def test_get_autolabels_by_run_with_range(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: DatabaseScenario,
    ) -> None:
        xianxia_autolabels_scenario.novels["novel"]
        user = xianxia_autolabels_scenario.users["owner"]
        run = xianxia_autolabels_scenario.autolabel_runs["cluener"]

        response = client.get(
            f"/auto-label-runs/{run.run_id}/auto-labels?start=1&end=2",
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        # Chapter numbers are 1-indexed, so start=1, end=2 picks chapter 1 only.
        assert len(payload) == 1


class TestCreateAutoLabelsRouter:
    def test_create_autolabels(
        self,
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
            "params": {
                "modelName": "cluener",
            },
        }
        request_key = uuid.uuid4()
        response = client.post(
            f"/auto-labels?requestKey={request_key}",
            json=body,
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()

        assert "run" in payload
        run = payload["run"]
        assert run["modelName"] == "cluener"
        assert run["novelId"] == str(novel.novel_id)
        assert run["triggeredBy"] == str(user.user_id)

        assert "autolabels" in payload
        assert len(payload["autolabels"]) == len(chapter_ids)
        for al in payload["autolabels"]:
            assert al["autoLabelMeta"]["autoLabelStatus"] == "pending"
            assert al["autoLabelMeta"]["runId"] == run["runId"]

        cached_response = client.get(f"/cached/{request_key}")
        assert cached_response.status_code == status.HTTP_200_OK
        cached_payload = cached_response.json()
        assert cached_payload["status"] == "success"
        assert cached_payload["status_code"] == status.HTTP_200_OK
        assert cached_payload["response"] == payload
        assert cached_payload["error"] is None

    def test_create_autolabels_different_novel(
        self,
        client: TestClient,
        scifi_scenario: DatabaseScenario,
        xianxia_scenario: DatabaseScenario,
    ) -> None:
        novel = scifi_scenario.novels["novel"]
        user = scifi_scenario.users["owner"]
        chapter_ids = [
            chapter.chapter_id for key, chapter in scifi_scenario.chapters.items() if key.startswith("novel:")
        ]
        assert len(chapter_ids) > 0

        body = {
            "novelId": str(novel.novel_id),
            "chapterIds": [str(cid) for cid in chapter_ids],
            "params": {
                "modelName": "cluener",
            },
        }
        response = client.post(
            "/auto-labels",
            json=body,
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert len(payload["autolabels"]) == len(chapter_ids)
        # Verify this is a DIFFERENT novel from the xianxia one.
        xianxia_novel_id = str(xianxia_scenario.novels["novel"].novel_id)
        assert payload["run"]["novelId"] == str(novel.novel_id)
        assert payload["run"]["novelId"] != xianxia_novel_id

    def test_create_autolabels_without_chapter_filter_is_scoped_to_requested_novel(
        self,
        client: TestClient,
        novel_permission_scenario: DatabaseScenario,
    ) -> None:
        target_novel = novel_permission_scenario.novels["put"]
        target_chapter = novel_permission_scenario.chapters["public"]

        response = client.post(
            "/auto-labels",
            json={
                "novelId": str(target_novel.novel_id),
                "params": {"modelName": "cluener"},
            },
            headers=_auth_headers(novel_permission_scenario.users["admin"]),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["run"]["novelId"] == str(target_novel.novel_id)
        assert [entry["chapterId"] for entry in payload["autolabels"]] == [str(target_chapter.chapter_id)]

    def test_novel_viewer_can_create_autolabels(
        self,
        client: TestClient,
        novel_permission_scenario: DatabaseScenario,
    ) -> None:
        novel = novel_permission_scenario.novels["ov"]
        content = novel_permission_scenario.contents["owner_viewer_v1"]
        response = client.post(
            "/auto-labels",
            json={
                "novelId": str(novel.novel_id),
                "chapterIds": [str(content.chapter_id)],
                "params": {"modelName": "cluener"},
            },
            headers=_auth_headers(novel_permission_scenario.users["other"]),
        )

        assert response.status_code == status.HTTP_200_OK
        assert [entry["chapterId"] for entry in response.json()["autolabels"]] == [str(content.chapter_id)]

    def test_public_novel_reader_cannot_create_autolabel_run(
        self,
        client: TestClient,
        test_db: Session,
        novel_permission_scenario: DatabaseScenario,
    ) -> None:
        novel = novel_permission_scenario.novels["put"]
        actor = novel_permission_scenario.users["other"]
        run_count_before = test_db.query(AutoLabelRun).count()

        response = client.post(
            "/auto-labels",
            json={
                "novelId": str(novel.novel_id),
                "params": {"modelName": "cluener"},
            },
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert test_db.query(AutoLabelRun).count() == run_count_before
