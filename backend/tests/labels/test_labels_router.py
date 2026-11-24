from datetime import timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.labels.models import LabelData
from src.novels.models import Chapter, ChapterContent
from test_support.test_data.scenarios import DatabaseScenario


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _label_groups_url(novel_id: object) -> str:
    return f"/label-groups?novelId={novel_id}"


def _label_url(label_id: object) -> str:
    return f"/labels/{label_id}"


class TestCreateLabelGroup:
    def test_owner_and_editor_can_create_label_group(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        novel = label_access_scenario.novels["private"]

        for user_key, group_name in (("owner", "Owner Created"), ("editor", "Editor Created")):
            response = client.post(
                "/label-groups",
                json={"novelId": str(novel.novel_id), "labelGroupName": group_name},
                headers=_auth_headers(label_access_scenario.users[user_key]),
            )

            assert response.status_code == status.HTTP_200_OK
            payload = response.json()
            assert payload["labelGroupName"] == group_name
            assert payload["novelId"] == str(novel.novel_id)

    def test_viewer_and_outsider_cannot_create_label_group(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        novel = label_access_scenario.novels["public"]

        for user_key in ("viewer", "outsider"):
            response = client.post(
                "/label-groups",
                json={"novelId": str(novel.novel_id), "labelGroupName": f"Denied {user_key}"},
                headers=_auth_headers(label_access_scenario.users[user_key]),
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadLabel:
    def test_owner_can_read_label(self, client: TestClient, label_access_scenario: DatabaseScenario) -> None:
        actor = label_access_scenario.users["owner"]
        label = label_access_scenario.labels["owner_test"]

        response = client.get(_label_url(label.label_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "labelDataId": str(label.label_data_id),
            "labelDirty": label.label_dirty,
            "labelEnd": label.label_end,
            "labelEntityGroup": label.label_entity_group,
            "labelId": str(label.label_id),
            "labelScore": label.label_score,
            "labelStart": label.label_start,
            "labelWord": label.label_word,
        }

    def test_novel_viewer_can_read_private_novel_label(
        self, client: TestClient, label_access_scenario: DatabaseScenario
    ) -> None:
        actor = label_access_scenario.users["viewer"]
        label = label_access_scenario.labels["private_test"]

        response = client.get(_label_url(label.label_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["labelId"] == str(label.label_id)

    def test_outsider_can_read_public_novel_label(
        self, client: TestClient, label_access_scenario: DatabaseScenario
    ) -> None:
        actor = label_access_scenario.users["outsider"]
        label = label_access_scenario.labels["owner_test"]

        response = client.get(_label_url(label.label_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["labelId"] == str(label.label_id)

    def test_outsider_cannot_read_private_novel_label(
        self, client: TestClient, label_access_scenario: DatabaseScenario
    ) -> None:
        actor = label_access_scenario.users["outsider"]
        label = label_access_scenario.labels["private_test"]

        response = client.get(_label_url(label.label_id), headers=_auth_headers(actor))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Label not found."

    def test_missing_label_gets_404(self, client: TestClient, label_access_scenario: DatabaseScenario) -> None:
        actor = label_access_scenario.users["owner"]

        response = client.get(
            _label_url("00000000-0000-0000-0000-000000000000"),
            headers=_auth_headers(actor),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Label not found."


class TestReadLabelDatas:
    def test_outsider_sees_only_public_chapter_label_datas_without_duplicates(
        self,
        client: TestClient,
        test_db: Session,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        novel = label_access_scenario.novels["public"]
        group = label_access_scenario.label_groups["owner_only"]
        private_chapter = Chapter(
            novel_id=novel.novel_id,
            chapter_num=2,
            chapter_title="Draft Chapter",
            chapter_is_public=False,
        )
        test_db.add(private_chapter)
        test_db.flush()
        private_content = ChapterContent(
            chapter_id=private_chapter.chapter_id,
            chapter_content_version=1,
            chapter_content_text="Draft chapter text.",
        )
        test_db.add(private_content)
        test_db.flush()
        private_label_data = LabelData(
            label_group_id=group.label_group_id,
            chapter_content_id=private_content.chapter_content_id,
        )
        test_db.add(private_label_data)
        test_db.commit()

        outsider_response = client.get(
            f"/label-datas?labelGroupId={group.label_group_id}",
            headers=_auth_headers(label_access_scenario.users["outsider"]),
        )
        viewer_response = client.get(
            f"/label-datas?labelGroupId={group.label_group_id}",
            headers=_auth_headers(label_access_scenario.users["viewer"]),
        )

        assert outsider_response.status_code == status.HTTP_200_OK
        assert [entry["labelDataId"] for entry in outsider_response.json()] == [
            str(label_access_scenario.label_datas["owner_only_data"].label_data_id)
        ]
        assert viewer_response.status_code == status.HTTP_200_OK
        assert {entry["labelDataId"] for entry in viewer_response.json()} == {
            str(label_access_scenario.label_datas["owner_only_data"].label_data_id),
            str(private_label_data.label_data_id),
        }


class TestReadLabelGroups:
    def test_contributors_and_admin_read_public_and_private_groups(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        for user_key in ("owner", "editor", "viewer", "admin"):
            actor = label_access_scenario.users[user_key]
            public_response = client.get(
                _label_groups_url(label_access_scenario.novels["public"].novel_id),
                headers=_auth_headers(actor),
            )
            private_response = client.get(
                _label_groups_url(label_access_scenario.novels["private"].novel_id),
                headers=_auth_headers(actor),
            )

            assert public_response.status_code == status.HTTP_200_OK
            assert {entry["labelGroupName"] for entry in public_response.json()} == {
                "Owner Only Group",
                "With Editor Group",
                "With Viewer Group",
            }
            assert private_response.status_code == status.HTTP_200_OK
            assert {entry["labelGroupName"] for entry in private_response.json()} == {
                "Private Novel Group",
            }

    def test_outsider_reads_public_groups_only(
        self,
        client: TestClient,
        label_access_scenario: DatabaseScenario,
    ) -> None:
        actor = label_access_scenario.users["outsider"]

        public_response = client.get(
            _label_groups_url(label_access_scenario.novels["public"].novel_id),
            headers=_auth_headers(actor),
        )
        private_response = client.get(
            _label_groups_url(label_access_scenario.novels["private"].novel_id),
            headers=_auth_headers(actor),
        )

        assert public_response.status_code == status.HTTP_200_OK
        assert {entry["labelGroupName"] for entry in public_response.json()} == {
            "Owner Only Group",
            "With Editor Group",
            "With Viewer Group",
        }
        assert private_response.status_code == status.HTTP_200_OK
        assert private_response.json() == []
