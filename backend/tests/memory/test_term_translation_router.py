from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.utils import create_access_token
from src.memory.models import MemoryGroup
from src.memory.plugins.glossary.models import GlossaryTerm
from src.memory.plugins.translations.models import TermTranslation
from src.memory.types import Creator, ReviewStatus
from test_support.test_data.scenarios import DatabaseScenario


def auth(user: User):
    return {"Authorization": "Bearer " + create_access_token({"sub": user.user_name}, timedelta(minutes=30))}


def group(db: Session, scenario: DatabaseScenario, novel_key: str = "ov"):
    row = MemoryGroup(
        memory_group_name="Translations", memory_language="zh", novel_id=scenario.novels[novel_key].novel_id
    )
    db.add(row)
    db.flush()
    return row


def test_batch_read_is_scoped_and_includes_rejected_mappings_for_review(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario
):
    scenario = novel_permission_scenario
    primary, other = group(test_db, scenario), group(test_db, scenario)
    terms = [
        GlossaryTerm(memory_group_id=primary.memory_group_id, term="Alpha"),
        GlossaryTerm(memory_group_id=primary.memory_group_id, term="Missing"),
        GlossaryTerm(memory_group_id=other.memory_group_id, term="Foreign"),
    ]
    test_db.add_all(terms)
    test_db.flush()
    test_db.add_all(
        [
            TermTranslation(
                term_id=terms[0].term_id,
                translation="Existing",
                creator_type=Creator.AGENT,
                review_status=ReviewStatus.REJECTED,
            ),
            TermTranslation(term_id=terms[2].term_id, translation="Hidden", creator_type=Creator.AGENT),
        ]
    )
    test_db.commit()
    url = f"/memory-groups/{primary.memory_group_id}/translations"
    params = {"termIds": [str(term.term_id) for term in terms] + [str(uuid4())]}
    response = client.get(url, params=params, headers=auth(scenario.users["other"]))
    assert response.status_code == 200
    assert [(row["termId"], row["translation"], row["reviewStatus"]) for row in response.json()] == [
        (str(terms[0].term_id), "Existing", "rejected")
    ]
    assert client.get(url, params=params).status_code == 404
    assert client.get(url, headers=auth(scenario.users["owner"])).status_code == 422
    assert (
        client.get(url, params={"termIds": [str(uuid4())] * 101}, headers=auth(scenario.users["owner"])).status_code
        == 422
    )


@pytest.mark.parametrize("review_status", list(ReviewStatus))
def test_manual_save_preserves_review_status_and_marks_creator_as_user(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario, review_status: ReviewStatus
):
    scenario = novel_permission_scenario
    memory_group = group(test_db, scenario)
    term = GlossaryTerm(memory_group_id=memory_group.memory_group_id, term="Alpha", review_status=ReviewStatus.APPROVED)
    test_db.add(term)
    test_db.flush()
    test_db.add(
        TermTranslation(
            term_id=term.term_id, translation="Old", creator_type=Creator.AGENT, review_status=review_status
        )
    )
    test_db.commit()
    url = f"/memory-groups/{memory_group.memory_group_id}/translations/{term.term_id}"
    response = client.put(url, json={"translation": "  New rendering  "}, headers=auth(scenario.users["owner"]))
    assert response.status_code == 200
    assert response.json()["translation"] == "New rendering"
    assert response.json()["reviewStatus"] == review_status.value
    assert response.json()["creatorType"] == "user"
    test_db.expire_all()
    source_term = test_db.get(GlossaryTerm, term.term_id)
    assert source_term is not None and source_term.review_status == ReviewStatus.APPROVED
    assert client.put(url, json={"translation": "Blocked"}, headers=auth(scenario.users["other"])).status_code == 404
    assert client.put(url, json={"translation": "Blocked"}).status_code == 401
    assert client.put(url, json={"translation": " \n "}, headers=auth(scenario.users["owner"])).status_code == 422
    test_db.expire_all()
    saved = test_db.get(TermTranslation, term.term_id)
    assert saved is not None and saved.translation == "New rendering"


def test_editor_can_fill_missing_mapping_without_creating_duplicates_or_crossing_groups(
    client: TestClient, test_db: Session, novel_permission_scenario: DatabaseScenario
):
    scenario = novel_permission_scenario
    primary, other = group(test_db, scenario, "oe"), group(test_db, scenario, "oe")
    term = GlossaryTerm(memory_group_id=primary.memory_group_id, term="Alpha")
    test_db.add(term)
    test_db.commit()
    headers = auth(scenario.users["other"])
    url = f"/memory-groups/{primary.memory_group_id}/translations/{term.term_id}"
    for translation in ("First", "Second"):
        response = client.put(url, json={"translation": translation}, headers=headers)
        assert response.status_code == 200
        assert response.json()["reviewStatus"] == "pending"
        assert response.json()["translation"] == translation
    assert (
        test_db.scalar(select(func.count()).select_from(TermTranslation).where(TermTranslation.term_id == term.term_id))
        == 1
    )
    assert (
        client.put(
            f"/memory-groups/{other.memory_group_id}/translations/{term.term_id}",
            json={"translation": "Wrong group"},
            headers=headers,
        ).status_code
        == 404
    )
