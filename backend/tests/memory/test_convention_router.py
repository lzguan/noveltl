from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.memory.models import MemoryGroup
from src.memory.plugins.conventions.models import TranslationConvention
from src.memory.plugins.conventions.types import ConventionCategory
from src.memory.types import Creator, ReviewStatus
from test_support.test_data.scenarios import DatabaseScenario


def auth(user: User):
    return {"Authorization": "Bearer " + create_access_token({"sub": user.user_name}, timedelta(minutes=30))}


def group(db: Session, scenario: DatabaseScenario, novel_key: str = "oe"):
    row = MemoryGroup(
        memory_group_name="Conventions", memory_language="zh", novel_id=scenario.novels[novel_key].novel_id
    )
    db.add(row)
    db.flush()
    return row


def convention(db: Session, memory_group: MemoryGroup, **values) -> TranslationConvention:
    row = TranslationConvention(
        memory_group_id=memory_group.memory_group_id,
        category=values.pop("category", ConventionCategory.NAMING),
        title=values.pop("title", "Floral codenames"),
        rule=values.pop("rule", "Use the established rendering, e.g. 樱 → Sakura."),
        creator_type=values.pop("creator_type", Creator.AGENT),
        **values,
    )
    db.add(row)
    db.flush()
    return row


def test_list_is_scoped_filterable_and_paginated(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario
):
    scenario = novel_permission_scenario
    primary, other = group(test_db, scenario, "ov"), group(test_db, scenario, "ov")
    naming = convention(test_db, primary, review_status=ReviewStatus.REJECTED)
    style = convention(test_db, primary, category=ConventionCategory.STYLE, title="Register")
    convention(test_db, other, title="Hidden")
    test_db.commit()
    url = f"/memory-groups/{primary.memory_group_id}/conventions"
    viewer = auth(scenario.users["other"])

    response = client.get(url, headers=viewer)
    assert response.status_code == 200
    assert response.json()["count"] == 2
    # Unfiltered reads include rejected conventions for review.
    statuses = {row["conventionId"]: row["reviewStatus"] for row in response.json()["rows"]}
    assert statuses == {str(naming.convention_id): "rejected", str(style.convention_id): "pending"}

    usable = client.get(url, params={"reviewStatuses": ["pending", "approved"]}, headers=viewer).json()
    assert (usable["count"], [row["title"] for row in usable["rows"]]) == (1, ["Register"])
    by_category = client.get(url, params={"category": "naming"}, headers=viewer).json()
    assert [row["conventionId"] for row in by_category["rows"]] == [str(naming.convention_id)]

    pages = [client.get(url, params={"skip": skip, "limit": 1}, headers=viewer).json() for skip in (0, 1)]
    assert [page["count"] for page in pages] == [2, 2]
    assert {row["conventionId"] for page in pages for row in page["rows"]} == set(statuses)
    # Without read access the group simply has no visible conventions, as with memories.
    assert client.get(url).json() == {"count": 0, "rows": []}


def test_create_strips_input_and_requires_edit_access(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario
):
    scenario = novel_permission_scenario
    editable, viewable = group(test_db, scenario, "oe"), group(test_db, scenario, "ov")
    test_db.commit()
    body = {"category": "naming", "title": "  Floral codenames ", "rule": " 樱 → Sakura ", "rationale": None}
    editor = auth(scenario.users["other"])

    response = client.post(f"/memory-groups/{editable.memory_group_id}/conventions", json=body, headers=editor)
    assert response.status_code == 201
    created = response.json()
    assert (created["title"], created["rule"], created["rationale"]) == ("Floral codenames", "樱 → Sakura", None)
    assert (created["reviewStatus"], created["creatorType"]) == ("pending", "user")

    viewer_url = f"/memory-groups/{viewable.memory_group_id}/conventions"
    assert client.post(viewer_url, json=body, headers=editor).status_code == 404
    assert client.post(viewer_url, json=body).status_code == 401
    for blank in ({"title": " "}, {"rule": "\n"}, {"rationale": "  "}):
        url = f"/memory-groups/{editable.memory_group_id}/conventions"
        assert client.post(url, json=body | blank, headers=editor).status_code == 422


@pytest.mark.parametrize("review_status", list(ReviewStatus))
def test_manual_edit_preserves_review_status_and_takes_ownership_from_agent(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario, review_status: ReviewStatus
):
    """Agent writers will only modify their own pending rows, so a human edit must claim the row."""
    scenario = novel_permission_scenario
    memory_group = group(test_db, scenario)
    row = convention(test_db, memory_group, review_status=review_status)
    test_db.commit()
    url = f"/memory-groups/{memory_group.memory_group_id}/conventions/{row.convention_id}"
    body = {"category": "style", "title": "Honorifics", "rule": "Keep -senpai.", "rationale": "Genre norm."}

    response = client.put(url, json=body, headers=auth(scenario.users["owner"]))
    assert response.status_code == 200
    assert response.json()["reviewStatus"] == review_status.value
    assert response.json()["creatorType"] == "user"
    test_db.expire_all()
    saved = test_db.get(TranslationConvention, row.convention_id)
    assert saved is not None
    assert (saved.category, saved.title, saved.rule, saved.rationale) == (
        ConventionCategory.STYLE,
        "Honorifics",
        "Keep -senpai.",
        "Genre norm.",
    )


def test_writes_cannot_cross_groups_or_bypass_edit_access(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario
):
    scenario = novel_permission_scenario
    editable, viewable = group(test_db, scenario, "oe"), group(test_db, scenario, "ov")
    in_viewable = convention(test_db, viewable)
    test_db.commit()
    editor = auth(scenario.users["other"])
    body = {"category": "naming", "title": "Changed", "rule": "Changed"}
    targets = [
        f"/memory-groups/{editable.memory_group_id}/conventions/{in_viewable.convention_id}",
        f"/memory-groups/{viewable.memory_group_id}/conventions/{in_viewable.convention_id}",
        f"/memory-groups/{editable.memory_group_id}/conventions/{uuid4()}",
    ]
    for url in targets:
        assert client.put(url, json=body, headers=editor).status_code == 404
        assert (
            client.patch(f"{url}/review-status", json={"reviewStatus": "approved"}, headers=editor).status_code == 404
        )
        assert client.delete(url, headers=editor).status_code == 404
    test_db.expire_all()
    untouched = test_db.get(TranslationConvention, in_viewable.convention_id)
    assert untouched is not None
    assert (untouched.title, untouched.review_status) == ("Floral codenames", ReviewStatus.PENDING)


def test_review_status_change_keeps_agent_ownership_and_delete_removes_row(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario
):
    scenario = novel_permission_scenario
    memory_group = group(test_db, scenario)
    convention_id = convention(test_db, memory_group).convention_id
    test_db.commit()
    url = f"/memory-groups/{memory_group.memory_group_id}/conventions/{convention_id}"
    editor = auth(scenario.users["other"])

    response = client.patch(f"{url}/review-status", json={"reviewStatus": "approved"}, headers=editor)
    assert response.status_code == 200
    assert (response.json()["reviewStatus"], response.json()["creatorType"]) == ("approved", "agent")

    assert client.delete(url, headers=editor).status_code == 204
    test_db.expire_all()
    assert test_db.get(TranslationConvention, convention_id) is None
    assert client.delete(url, headers=editor).status_code == 404
