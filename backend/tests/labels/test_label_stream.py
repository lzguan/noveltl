from datetime import timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.labels.models import Label, LabelData
from test_support.test_data.scenarios import DatabaseScenario


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.user_name}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


def _patch_labels(
    client: TestClient,
    actor: User,
    label_data: LabelData,
    ops: list[dict[str, object]],
):
    return client.patch(
        f"/label-datas/{label_data.label_data_id}",
        headers=_auth_headers(actor),
        json={"ops": ops},
    )


def test_add_derives_word_from_immutable_chapter_content(
    client: TestClient,
    test_db: Session,
    label_access_scenario: DatabaseScenario,
) -> None:
    actor = label_access_scenario.users["owner"]
    label_data = label_access_scenario.label_datas["owner_only_data"]

    response = _patch_labels(
        client,
        actor,
        label_data,
        [
            {
                "op": "add",
                "startPos": 0,
                "endPos": 4,
                "dirty": False,
                "entityGroup": "PREFIX",
                "score": 0,
            }
        ],
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    added = test_db.execute(
        select(Label).where(
            Label.label_data_id == label_data.label_data_id,
            Label.label_start == 0,
            Label.label_end == 4,
        )
    ).scalar_one()
    assert added.label_word == "This"
    assert added.label_dirty is False
    assert added.label_score == 0


def test_update_targets_label_id_and_accepts_falsy_values(
    client: TestClient,
    test_db: Session,
    label_access_scenario: DatabaseScenario,
) -> None:
    actor = label_access_scenario.users["owner"]
    label_data = label_access_scenario.label_datas["owner_only_data"]
    label = label_access_scenario.labels["owner_test"]
    label.label_dirty = True
    test_db.commit()

    response = _patch_labels(
        client,
        actor,
        label_data,
        [
            {
                "op": "update",
                "labelId": str(label.label_id),
                "startPos": 0,
                "dirty": False,
                "score": 0,
            }
        ],
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    test_db.expire_all()
    updated = test_db.get(Label, label.label_id)
    assert updated is not None
    assert updated.label_start == 0
    assert updated.label_end == 12
    assert updated.label_word == "This is test"
    assert updated.label_dirty is False
    assert updated.label_score == 0


def test_update_rejects_label_from_another_label_data(
    client: TestClient,
    test_db: Session,
    label_access_scenario: DatabaseScenario,
) -> None:
    actor = label_access_scenario.users["owner"]
    target_label_data = label_access_scenario.label_datas["owner_only_data"]
    other_label = label_access_scenario.labels["editor_test"]

    response = _patch_labels(
        client,
        actor,
        target_label_data,
        [
            {
                "op": "update",
                "labelId": str(other_label.label_id),
                "entityGroup": "CHANGED",
            }
        ],
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    test_db.expire_all()
    unchanged = test_db.get(Label, other_label.label_id)
    assert unchanged is not None
    assert unchanged.label_entity_group != "CHANGED"


def test_update_rejects_invalid_combined_range(
    client: TestClient,
    test_db: Session,
    label_access_scenario: DatabaseScenario,
) -> None:
    actor = label_access_scenario.users["owner"]
    label_data = label_access_scenario.label_datas["owner_only_data"]
    label = label_access_scenario.labels["owner_test"]

    response = _patch_labels(
        client,
        actor,
        label_data,
        [
            {
                "op": "update",
                "labelId": str(label.label_id),
                "startPos": label.label_end,
            }
        ],
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    test_db.expire_all()
    unchanged = test_db.get(Label, label.label_id)
    assert unchanged is not None
    assert (unchanged.label_start, unchanged.label_end) == (8, 12)


def test_delete_targets_label_id(
    client: TestClient,
    test_db: Session,
    label_access_scenario: DatabaseScenario,
) -> None:
    actor = label_access_scenario.users["owner"]
    label_data = label_access_scenario.label_datas["owner_only_data"]
    label = label_access_scenario.labels["owner_test"]

    response = _patch_labels(
        client,
        actor,
        label_data,
        [{"op": "delete", "labelId": str(label.label_id)}],
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    test_db.expire_all()
    assert test_db.get(Label, label.label_id) is None


def test_viewer_cannot_update_label(
    client: TestClient,
    test_db: Session,
    label_access_scenario: DatabaseScenario,
) -> None:
    actor = label_access_scenario.users["collaborator"]
    label_data = label_access_scenario.label_datas["with_viewer_data"]
    label = label_access_scenario.labels["viewer_test"]

    response = _patch_labels(
        client,
        actor,
        label_data,
        [
            {
                "op": "update",
                "labelId": str(label.label_id),
                "entityGroup": "CHANGED",
            }
        ],
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    test_db.expire_all()
    unchanged = test_db.get(Label, label.label_id)
    assert unchanged is not None
    assert unchanged.label_entity_group != "CHANGED"


def test_stream_rolls_back_earlier_operations_when_later_operation_fails(
    client: TestClient,
    test_db: Session,
    label_access_scenario: DatabaseScenario,
) -> None:
    actor = label_access_scenario.users["owner"]
    label_data = label_access_scenario.label_datas["owner_only_data"]
    label = label_access_scenario.labels["owner_test"]

    response = _patch_labels(
        client,
        actor,
        label_data,
        [
            {"op": "delete", "labelId": str(label.label_id)},
            {
                "op": "add",
                "startPos": 0,
                "endPos": 100,
            },
        ],
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    test_db.expire_all()
    assert test_db.get(Label, label.label_id) is not None
