import uuid
from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.autolabels.constants import AutoLabelProgress
from src.autolabels.models import AutoLabel
from tests.fixtures.bundles import ScenarioBundle
from tests.gate_logging import log_gate

pytestmark = pytest.mark.dependency(
    depends=["gate::fixture_validation"],
    scope="session",
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


class TestAutoLabelRunsRouter:
    @pytest.mark.dependency(name="autolabels::router::list_runs", scope="session")
    def test_list_runs(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = xianxia_autolabels_scenario.novels[0]
        user = novel_bundle.user

        response = client.get(
            f"/auto-label-runs?novelId={novel_bundle.novel.novel_id}",
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

    @pytest.mark.dependency(name="autolabels::router::list_runs_mine", scope="session")
    def test_list_runs_mine(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = xianxia_autolabels_scenario.novels[0]
        user = novel_bundle.user

        response = client.get(
            f"/auto-label-runs?novelId={novel_bundle.novel.novel_id}&mine=true",
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        for run in payload:
            assert run["triggeredBy"] == str(user.user_id)


class TestAutoLabelRouter:
    @pytest.mark.dependency(name="autolabels::router::get_by_id", scope="session")
    def test_get_autolabel_by_id(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = xianxia_autolabels_scenario.novels[0]
        user = novel_bundle.user
        autolabel = novel_bundle.autolabels_by_name["cluener"][0]

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

    @pytest.mark.dependency(name="autolabels::router::get_by_id_not_found", scope="session")
    def test_get_autolabel_by_id_not_found(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = xianxia_autolabels_scenario.novels[0]
        user = novel_bundle.user
        fake_id = uuid.uuid4()

        response = client.get(
            f"/auto-labels/{fake_id}",
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAutoLabelsByRunRouter:
    @pytest.mark.dependency(name="autolabels::router::autolabels_by_run", scope="session")
    def test_get_autolabels_by_run(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = xianxia_autolabels_scenario.novels[0]
        user = novel_bundle.user
        run = novel_bundle.autolabel_runs_by_name["cluener"]
        expected_count = len(novel_bundle.autolabels_by_name["cluener"])

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

    @pytest.mark.dependency(name="autolabels::router::autolabels_by_run_with_range", scope="session")
    def test_get_autolabels_by_run_with_range(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = xianxia_autolabels_scenario.novels[0]
        user = novel_bundle.user
        run = novel_bundle.autolabel_runs_by_name["cluener"]

        response = client.get(
            f"/auto-label-runs/{run.run_id}/auto-labels?start=1&end=2",
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        # Chapter numbers are 1-indexed, so start=1, end=2 picks chapter 1 only.
        assert len(payload) == 1


class TestCreateAutoLabelsRouter:
    @pytest.mark.dependency(name="autolabels::router::create", scope="session")
    def test_create_autolabels(
        self,
        client: TestClient,
        xianxia_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = xianxia_scenario.novels[0]
        user = novel_bundle.user
        chapter_ids = [cb.chapter.chapter_id for cb in novel_bundle.chapters]
        assert len(chapter_ids) > 0

        body = {
            "novelId": str(novel_bundle.novel.novel_id),
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
        assert run["novelId"] == str(novel_bundle.novel.novel_id)
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

    @pytest.mark.dependency(name="autolabels::router::create_scifi_novel", scope="session")
    def test_create_autolabels_different_novel(
        self,
        client: TestClient,
        scifi_scenario: ScenarioBundle,
        xianxia_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = scifi_scenario.novels[0]
        user = novel_bundle.user
        chapter_ids = [cb.chapter.chapter_id for cb in novel_bundle.chapters]
        assert len(chapter_ids) > 0

        body = {
            "novelId": str(novel_bundle.novel.novel_id),
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
        xianxia_novel_id = str(xianxia_scenario.novels[0].novel.novel_id)
        assert payload["run"]["novelId"] == str(novel_bundle.novel.novel_id)
        assert payload["run"]["novelId"] != xianxia_novel_id

    @pytest.mark.dependency(name="autolabels::router::create_scoped_to_novel", scope="session")
    def test_create_autolabels_without_chapter_filter_is_scoped_to_requested_novel(
        self,
        client: TestClient,
        novel_resource_scenario: ScenarioBundle,
        p1_admin: User,
    ) -> None:
        target_novel = novel_resource_scenario.novels_by_title["pt"]
        target_chapter = novel_resource_scenario.chapters_by_title["Public Ch1"]

        response = client.post(
            "/auto-labels",
            json={
                "novelId": str(target_novel.novel.novel_id),
                "params": {"modelName": "cluener"},
            },
            headers=_auth_headers(p1_admin),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["run"]["novelId"] == str(target_novel.novel.novel_id)
        assert [entry["chapterId"] for entry in payload["autolabels"]] == [
            str(target_chapter.chapter.chapter_id)
        ]


class TestPromoteAutoLabelsRouter:
    @pytest.mark.dependency(name="autolabels::router::promote", scope="session")
    def test_promote_autolabels(
        self,
        client: TestClient,
        xianxia_autolabels_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = xianxia_autolabels_scenario.novels[0]
        label_bundle = novel_bundle.label_groups[0]
        user = novel_bundle.user
        run_id = novel_bundle.autolabel_runs_by_name["cluener"].run_id
        expected_chapters = len(novel_bundle.autolabels_by_name["cluener"])

        body = {
            "runId": str(run_id),
        }
        response = client.post(
            f"/label-groups/{label_bundle.label_group.label_group_id}/label-datas/auto-labels",
            json=body,
            headers=_auth_headers(user),
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert len(payload["errors"]) == 0
        assert len(payload["success"]) == expected_chapters

    @pytest.mark.dependency(name="autolabels::router::promote_scoped_to_novel", scope="session")
    def test_promote_autolabels_ignores_cross_novel_rows_in_run(
        self,
        client: TestClient,
        test_db: Session,
        xianxia_autolabels_scenario: ScenarioBundle,
        scifi_scenario: ScenarioBundle,
    ) -> None:
        novel_bundle = xianxia_autolabels_scenario.novels[0]
        label_bundle = novel_bundle.label_groups[0]
        run_id = novel_bundle.autolabel_runs_by_name["cluener"].run_id
        foreign_content = scifi_scenario.novels[0].chapter_content
        test_db.add(
            AutoLabel(
                auto_label_data=[],
                auto_label_status=AutoLabelProgress.DONE,
                chapter_content_id=foreign_content.chapter_content_id,
                run_id=run_id,
            )
        )
        test_db.commit()

        response = client.post(
            f"/label-groups/{label_bundle.label_group.label_group_id}/label-datas/auto-labels",
            json={"runId": str(run_id)},
            headers=_auth_headers(novel_bundle.user),
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert len(payload["errors"]) == 0
        assert len(payload["success"]) == len(novel_bundle.autolabels_by_name["cluener"])
        promoted_content_ids = {content_id for _, content_id in payload["success"]}
        assert str(foreign_content.chapter_content_id) not in promoted_content_ids


@pytest.mark.dependency(
    name="gate::autolabels::router",
    depends=[
        "autolabels::router::list_runs",
        "autolabels::router::list_runs_mine",
        "autolabels::router::get_by_id",
        "autolabels::router::get_by_id_not_found",
        "autolabels::router::autolabels_by_run",
        "autolabels::router::autolabels_by_run_with_range",
        "autolabels::router::create",
        "autolabels::router::create_scifi_novel",
        "autolabels::router::create_scoped_to_novel",
        "autolabels::router::promote",
        "autolabels::router::promote_scoped_to_novel",
    ],
    scope="session",
)
def test_gate():
    log_gate("gate::autolabels::router")
