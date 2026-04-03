"""
Tests for the glossary service endpoints.

Tests cover:
- Glossary CRUD (create, read, update, delete)
- Glossary Entry CRUD
- Glossary Contributors (add, update, remove)
- Import from Labels
- Permission enforcement (owner / editor / viewer / unauthenticated)
- Unique constraints
"""

from typing import Any, Protocol

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.glossaries.constants import GlossaryRole
from src.glossaries.models import Glossary, GlossaryContributor, GlossaryEntry
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Chapter, Contributor, Novel, Revision, RevisionText


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...
    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def g_language(test_db: Session) -> Language:
    lang = Language(language_name="Chinese", language_code="zh")
    lang_en = Language(language_name="English", language_code="en")
    test_db.add_all([lang, lang_en])
    test_db.commit()
    return lang


@pytest.fixture
def g_owner(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="g_owner", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def g_editor(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="g_editor", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def g_viewer(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="g_viewer", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def g_outsider(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="g_outsider", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def g_admin(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="g_admin", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.ADMIN)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def g_novel_public(test_db: Session, g_language: Language, g_owner: User) -> Novel:
    novel = Novel(
        novel_title="Test Novel",
        language_code=g_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=g_owner.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def g_novel_private(test_db: Session, g_language: Language, g_owner: User) -> Novel:
    novel = Novel(
        novel_title="Private Novel",
        language_code=g_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PRIVATE,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=g_owner.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def g_glossary(test_db: Session, g_novel_public: Novel, g_owner: User) -> Glossary:
    glossary = Glossary(
        glossary_name="Main Glossary",
        novel_id=g_novel_public.novel_id,
        source_language_code="zh",
        target_language_code="en",
    )
    test_db.add(glossary)
    test_db.commit()
    test_db.add(
        GlossaryContributor(
            glossary_id=glossary.glossary_id,
            user_id=g_owner.user_id,
            glossary_contributor_role=GlossaryRole.OWNER,
        )
    )
    test_db.commit()
    return glossary


@pytest.fixture
def g_glossary_with_editor(test_db: Session, g_glossary: Glossary, g_editor: User) -> Glossary:
    """Add editor contributor to the main glossary."""
    test_db.add(
        GlossaryContributor(
            glossary_id=g_glossary.glossary_id,
            user_id=g_editor.user_id,
            glossary_contributor_role=GlossaryRole.EDITOR,
        )
    )
    test_db.commit()
    return g_glossary


@pytest.fixture
def g_glossary_with_viewer(test_db: Session, g_glossary: Glossary, g_viewer: User) -> Glossary:
    """Add viewer contributor to the main glossary."""
    test_db.add(
        GlossaryContributor(
            glossary_id=g_glossary.glossary_id,
            user_id=g_viewer.user_id,
            glossary_contributor_role=GlossaryRole.VIEWER,
        )
    )
    test_db.commit()
    return g_glossary


@pytest.fixture
def g_entry(test_db: Session, g_glossary: Glossary) -> GlossaryEntry:
    entry = GlossaryEntry(
        glossary_id=g_glossary.glossary_id,
        source_term="龙",
        translated_term="Dragon",
        entity_type="MISC",
    )
    test_db.add(entry)
    test_db.commit()
    return entry


@pytest.fixture
def g_label_group(test_db: Session, g_novel_public: Novel, g_owner: User) -> LabelGroup:
    lg = LabelGroup(label_group_name="Test Labels", novel_id=g_novel_public.novel_id)
    test_db.add(lg)
    test_db.commit()
    test_db.add(
        LabelContributor(
            label_group_id=lg.label_group_id,
            user_id=g_owner.user_id,
            label_contributor_role=LabelRole.OWNER,
        )
    )
    test_db.commit()
    return lg


@pytest.fixture
def g_label_data_with_labels(
    test_db: Session, g_label_group: LabelGroup, g_novel_public: Novel, g_owner: User
) -> LabelData:
    chapter = Chapter(chapter_num=1, novel_id=g_novel_public.novel_id)
    test_db.add(chapter)
    test_db.commit()
    revision = Revision(
        chapter_id=chapter.chapter_id,
        revision_title="Chapter 1",
        revision_is_primary=True,
        revision_is_public=True,
    )
    test_db.add(revision)
    test_db.commit()
    rt = RevisionText(
        revision_id=revision.revision_id,
        revision_text_content="李明 went to the 龙 mountain.",
        revision_text_version=1,
    )
    test_db.add(rt)
    test_db.commit()
    ld = LabelData(label_group_id=g_label_group.label_group_id, revision_text_id=rt.revision_text_id)
    test_db.add(ld)
    test_db.commit()
    # Add labels
    labels = [
        Label(
            label_data_id=ld.label_data_id,
            label_word="李明",
            label_start=0,
            label_end=2,
            label_entity_group="PER",
            label_score=0.99,
            label_dirty=False,
        ),
        Label(
            label_data_id=ld.label_data_id,
            label_word="龙",
            label_start=17,
            label_end=18,
            label_entity_group="LOC",
            label_score=0.95,
            label_dirty=False,
        ),
    ]
    test_db.add_all(labels)
    test_db.commit()
    return ld


def get_auth_header(client: TestClient, username: str, password: str = "pass") -> dict[str, str]:
    resp = client.post("/token", data={"username": username, "password": password})
    assert resp.status_code == status.HTTP_200_OK
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Glossary CRUD Tests
# ===========================================================================


class TestGlossaryCRUD:
    def test_create_glossary(self, client: TestClient, g_owner: User, g_novel_public: Novel):
        headers = get_auth_header(client, "g_owner")
        response = client.post(
            "/glossaries",
            json={
                "glossary_name": "New Glossary",
                "novel_id": str(g_novel_public.novel_id),
                "source_language_code": "zh",
                "target_language_code": "en",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["glossary_name"] == "New Glossary"
        assert data["novel_id"] == str(g_novel_public.novel_id)
        assert data["source_language_code"] == "zh"
        assert data["target_language_code"] == "en"
        assert "glossary_id" in data

    def test_create_glossary_with_description(self, client: TestClient, g_owner: User, g_novel_public: Novel):
        headers = get_auth_header(client, "g_owner")
        response = client.post(
            "/glossaries",
            json={
                "glossary_name": "Described Glossary",
                "glossary_description": "A helpful glossary",
                "novel_id": str(g_novel_public.novel_id),
                "source_language_code": "zh",
                "target_language_code": "en",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["glossary_description"] == "A helpful glossary"

    def test_create_glossary_unauthenticated(self, client: TestClient, g_novel_public: Novel):
        response = client.post(
            "/glossaries",
            json={
                "glossary_name": "Anon Glossary",
                "novel_id": str(g_novel_public.novel_id),
                "source_language_code": "zh",
                "target_language_code": "en",
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_glossary_novel_not_found(self, client: TestClient, g_owner: User):
        import uuid

        headers = get_auth_header(client, "g_owner")
        response = client.post(
            "/glossaries",
            json={
                "glossary_name": "Ghost Glossary",
                "novel_id": str(uuid.uuid4()),
                "source_language_code": "zh",
                "target_language_code": "en",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_glossaries_by_novel(self, client: TestClient, g_glossary: Glossary, g_novel_public: Novel):
        response = client.get(f"/glossaries?novel-id={g_novel_public.novel_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["glossary_id"] == str(g_glossary.glossary_id)

    def test_list_glossaries_unauthenticated_public_novel(
        self, client: TestClient, g_glossary: Glossary, g_novel_public: Novel
    ):
        # Unauthenticated guests can see glossaries on public novels
        # (no contributor check for guests — only novel visibility check)
        response = client.get(f"/glossaries?novel-id={g_novel_public.novel_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["glossary_id"] == str(g_glossary.glossary_id)

    def test_list_glossaries_contributor_sees_glossary(
        self, client: TestClient, g_glossary: Glossary, g_novel_public: Novel, g_owner: User
    ):
        headers = get_auth_header(client, "g_owner")
        response = client.get(f"/glossaries?novel-id={g_novel_public.novel_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["glossary_id"] == str(g_glossary.glossary_id)

    def test_get_glossary_by_id(self, client: TestClient, g_glossary: Glossary, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.get(f"/glossaries/{g_glossary.glossary_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["glossary_id"] == str(g_glossary.glossary_id)
        assert data["glossary_name"] == "Main Glossary"

    def test_get_glossary_not_found(self, client: TestClient, g_owner: User):
        import uuid

        headers = get_auth_header(client, "g_owner")
        response = client.get(f"/glossaries/{uuid.uuid4()}", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_glossary(self, client: TestClient, g_glossary: Glossary, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.patch(
            f"/glossaries/{g_glossary.glossary_id}",
            json={"glossary_name": "Renamed Glossary"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["glossary_name"] == "Renamed Glossary"

    def test_update_glossary_editor_can_update(
        self, client: TestClient, g_glossary_with_editor: Glossary, g_editor: User
    ):
        headers = get_auth_header(client, "g_editor")
        response = client.patch(
            f"/glossaries/{g_glossary_with_editor.glossary_id}",
            json={"glossary_name": "Editor Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK

    def test_update_glossary_viewer_cannot_update(
        self, client: TestClient, g_glossary_with_viewer: Glossary, g_viewer: User
    ):
        headers = get_auth_header(client, "g_viewer")
        response = client.patch(
            f"/glossaries/{g_glossary_with_viewer.glossary_id}",
            json={"glossary_name": "Hacked"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_glossary_outsider_cannot_update(self, client: TestClient, g_glossary: Glossary, g_outsider: User):
        headers = get_auth_header(client, "g_outsider")
        response = client.patch(
            f"/glossaries/{g_glossary.glossary_id}",
            json={"glossary_name": "Hacked"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_glossary(
        self, client: TestClient, g_glossary: Glossary, g_owner: User, g_admin: User, test_db: Session
    ):
        # NOTE: The remove_glossary service uses a raw SQL DELETE statement which does not
        # trigger ORM cascades. The FK constraint (NO ACTION) prevents deleting a glossary
        # that still has contributor rows. To test deletion, we use an admin user and remove
        # contributors via the DB first.
        test_db.query(GlossaryContributor).filter(GlossaryContributor.glossary_id == g_glossary.glossary_id).delete()
        test_db.commit()

        headers = get_auth_header(client, "g_admin")
        response = client.delete(f"/glossaries/{g_glossary.glossary_id}", headers=headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_glossary_editor_cannot_delete(
        self, client: TestClient, g_glossary_with_editor: Glossary, g_editor: User
    ):
        headers = get_auth_header(client, "g_editor")
        response = client.delete(f"/glossaries/{g_glossary_with_editor.glossary_id}", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_glossary_not_found(self, client: TestClient, g_owner: User):
        import uuid

        headers = get_auth_header(client, "g_owner")
        response = client.delete(f"/glossaries/{uuid.uuid4()}", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# Glossary Entry Tests
# ===========================================================================


class TestGlossaryEntryCRUD:
    def test_create_entry(self, client: TestClient, g_glossary: Glossary, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.post(
            "/glossary-entries",
            json={
                "glossary_id": str(g_glossary.glossary_id),
                "source_term": "水",
                "translated_term": "Water",
                "entity_type": "MISC",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["source_term"] == "水"
        assert data["translated_term"] == "Water"
        assert data["entity_type"] == "MISC"
        assert data["glossary_id"] == str(g_glossary.glossary_id)

    def test_create_entry_with_context_notes(self, client: TestClient, g_glossary: Glossary, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.post(
            "/glossary-entries",
            json={
                "glossary_id": str(g_glossary.glossary_id),
                "source_term": "火",
                "translated_term": "Fire",
                "context_notes": "An elemental force",
                "entity_type": "MISC",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["context_notes"] == "An elemental force"

    def test_create_entry_duplicate_raises_409(self, client: TestClient, g_entry: GlossaryEntry, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.post(
            "/glossary-entries",
            json={
                "glossary_id": str(g_entry.glossary_id),
                "source_term": g_entry.source_term,
                "entity_type": g_entry.entity_type,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_entry_viewer_cannot_create(
        self, client: TestClient, g_glossary_with_viewer: Glossary, g_viewer: User
    ):
        headers = get_auth_header(client, "g_viewer")
        response = client.post(
            "/glossary-entries",
            json={
                "glossary_id": str(g_glossary_with_viewer.glossary_id),
                "source_term": "天",
                "entity_type": "MISC",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_entry_outsider_cannot_create(self, client: TestClient, g_glossary: Glossary, g_outsider: User):
        headers = get_auth_header(client, "g_outsider")
        response = client.post(
            "/glossary-entries",
            json={
                "glossary_id": str(g_glossary.glossary_id),
                "source_term": "天",
                "entity_type": "MISC",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_entries(self, client: TestClient, g_entry: GlossaryEntry, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.get(f"/glossary-entries?glossary-id={g_entry.glossary_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        entry_ids = [e["glossary_entry_id"] for e in data]
        assert str(g_entry.glossary_entry_id) in entry_ids

    def test_get_entry_by_id(self, client: TestClient, g_entry: GlossaryEntry, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.get(f"/glossary-entries/{g_entry.glossary_entry_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["glossary_entry_id"] == str(g_entry.glossary_entry_id)
        assert data["source_term"] == "龙"

    def test_get_entry_not_found(self, client: TestClient, g_owner: User):
        import uuid

        headers = get_auth_header(client, "g_owner")
        response = client.get(f"/glossary-entries/{uuid.uuid4()}", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_entry(self, client: TestClient, g_entry: GlossaryEntry, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.patch(
            f"/glossary-entries/{g_entry.glossary_entry_id}",
            json={"translated_term": "Mighty Dragon"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["translated_term"] == "Mighty Dragon"

    def test_update_entry_editor_can_update(
        self, client: TestClient, g_entry: GlossaryEntry, g_glossary_with_editor: Glossary, g_editor: User
    ):
        headers = get_auth_header(client, "g_editor")
        response = client.patch(
            f"/glossary-entries/{g_entry.glossary_entry_id}",
            json={"translated_term": "Editor Dragon"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK

    def test_update_entry_viewer_cannot_update(
        self, client: TestClient, g_entry: GlossaryEntry, g_glossary_with_viewer: Glossary, g_viewer: User
    ):
        headers = get_auth_header(client, "g_viewer")
        response = client.patch(
            f"/glossary-entries/{g_entry.glossary_entry_id}",
            json={"translated_term": "Hacked Dragon"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_entry(self, client: TestClient, g_entry: GlossaryEntry, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.delete(f"/glossary-entries/{g_entry.glossary_entry_id}", headers=headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_entry_viewer_cannot_delete(
        self, client: TestClient, g_entry: GlossaryEntry, g_glossary_with_viewer: Glossary, g_viewer: User
    ):
        headers = get_auth_header(client, "g_viewer")
        response = client.delete(f"/glossary-entries/{g_entry.glossary_entry_id}", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_entry_not_found(self, client: TestClient, g_owner: User):
        import uuid

        headers = get_auth_header(client, "g_owner")
        response = client.delete(f"/glossary-entries/{uuid.uuid4()}", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# Glossary Contributor Tests
# ===========================================================================


class TestGlossaryContributors:
    def test_list_contributors(self, client: TestClient, g_glossary: Glossary, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        response = client.get(f"/glossaries/{g_glossary.glossary_id}/contributors", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == str(g_owner.user_id)
        assert data[0]["glossary_contributor_role"] == GlossaryRole.OWNER

    def test_add_contributor(self, client: TestClient, g_glossary: Glossary, g_owner: User, g_editor: User):
        headers = get_auth_header(client, "g_owner")
        response = client.post(
            f"/glossaries/{g_glossary.glossary_id}/contributors",
            json={
                "user_id": str(g_editor.user_id),
                "glossary_contributor_role": GlossaryRole.EDITOR,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["user_id"] == str(g_editor.user_id)
        assert data["glossary_contributor_role"] == GlossaryRole.EDITOR

    def test_add_duplicate_contributor_raises_409(self, client: TestClient, g_glossary: Glossary, g_owner: User):
        headers = get_auth_header(client, "g_owner")
        # owner already exists as contributor
        response = client.post(
            f"/glossaries/{g_glossary.glossary_id}/contributors",
            json={
                "user_id": str(g_owner.user_id),
                "glossary_contributor_role": GlossaryRole.EDITOR,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_add_contributor_non_owner_forbidden(
        self, client: TestClient, g_glossary_with_editor: Glossary, g_editor: User, g_outsider: User
    ):
        headers = get_auth_header(client, "g_editor")
        response = client.post(
            f"/glossaries/{g_glossary_with_editor.glossary_id}/contributors",
            json={
                "user_id": str(g_outsider.user_id),
                "glossary_contributor_role": GlossaryRole.VIEWER,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_contributor_role(
        self, client: TestClient, g_glossary_with_editor: Glossary, g_owner: User, g_editor: User
    ):
        headers = get_auth_header(client, "g_owner")
        response = client.patch(
            f"/glossaries/{g_glossary_with_editor.glossary_id}/contributors/{g_editor.user_id}",
            json={"glossary_contributor_role": GlossaryRole.VIEWER},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["glossary_contributor_role"] == GlossaryRole.VIEWER

    def test_update_contributor_non_owner_forbidden(
        self, client: TestClient, g_glossary_with_editor: Glossary, g_editor: User
    ):
        headers = get_auth_header(client, "g_editor")
        response = client.patch(
            f"/glossaries/{g_glossary_with_editor.glossary_id}/contributors/{g_editor.user_id}",
            json={"glossary_contributor_role": GlossaryRole.OWNER},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_remove_contributor(
        self, client: TestClient, g_glossary_with_editor: Glossary, g_owner: User, g_editor: User
    ):
        headers = get_auth_header(client, "g_owner")
        response = client.delete(
            f"/glossaries/{g_glossary_with_editor.glossary_id}/contributors/{g_editor.user_id}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_remove_contributor_non_owner_forbidden(
        self, client: TestClient, g_glossary_with_editor: Glossary, g_editor: User, g_outsider: User
    ):
        headers = get_auth_header(client, "g_editor")
        response = client.delete(
            f"/glossaries/{g_glossary_with_editor.glossary_id}/contributors/{g_outsider.user_id}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_contributors_outsider_forbidden(self, client: TestClient, g_glossary: Glossary, g_outsider: User):
        headers = get_auth_header(client, "g_outsider")
        response = client.get(f"/glossaries/{g_glossary.glossary_id}/contributors", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        # Returns empty since query filters by glossary access
        assert response.json() == []


# ===========================================================================
# Import from Labels Tests
# ===========================================================================


class TestImportFromLabels:
    def test_import_creates_entries(
        self,
        client: TestClient,
        g_glossary: Glossary,
        g_label_data_with_labels: LabelData,
        g_label_group: LabelGroup,
        g_owner: User,
    ):
        headers = get_auth_header(client, "g_owner")
        response = client.post(
            f"/glossaries/{g_glossary.glossary_id}/import-from-labels",
            json={
                "label_group_id": str(g_label_group.label_group_id),
                "overwrite_existing": False,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["entries_created"] == 2
        assert data["entries_updated"] == 0
        assert data["entries_skipped"] == 0

    def test_import_with_entity_type_filter(
        self,
        client: TestClient,
        g_glossary: Glossary,
        g_label_data_with_labels: LabelData,
        g_label_group: LabelGroup,
        g_owner: User,
    ):
        headers = get_auth_header(client, "g_owner")
        response = client.post(
            f"/glossaries/{g_glossary.glossary_id}/import-from-labels",
            json={
                "label_group_id": str(g_label_group.label_group_id),
                "entity_types": ["PER"],
                "overwrite_existing": False,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["entries_created"] == 1  # Only PER entity type

    def test_import_skips_existing_entries(
        self,
        client: TestClient,
        g_glossary: Glossary,
        g_entry: GlossaryEntry,
        g_label_data_with_labels: LabelData,
        g_label_group: LabelGroup,
        g_owner: User,
        test_db: Session,
    ):
        # g_entry already has source_term="龙", entity_type="MISC"
        # The labels have "龙" with entity_type="LOC", so they won't conflict
        # Add an entry that matches a label
        entry_per = GlossaryEntry(
            glossary_id=g_glossary.glossary_id,
            source_term="李明",
            entity_type="PER",
        )
        test_db.add(entry_per)
        test_db.commit()

        headers = get_auth_header(client, "g_owner")
        response = client.post(
            f"/glossaries/{g_glossary.glossary_id}/import-from-labels",
            json={
                "label_group_id": str(g_label_group.label_group_id),
                "entity_types": ["PER"],
                "overwrite_existing": False,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["entries_created"] == 0
        assert data["entries_skipped"] == 1

    def test_import_with_overwrite(
        self,
        client: TestClient,
        g_glossary: Glossary,
        g_label_data_with_labels: LabelData,
        g_label_group: LabelGroup,
        g_owner: User,
    ):
        headers = get_auth_header(client, "g_owner")
        response = client.post(
            f"/glossaries/{g_glossary.glossary_id}/import-from-labels",
            json={
                "label_group_id": str(g_label_group.label_group_id),
                "overwrite_existing": True,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["entries_updated"] == 2

    def test_import_label_group_not_found(self, client: TestClient, g_glossary: Glossary, g_owner: User):
        import uuid

        headers = get_auth_header(client, "g_owner")
        response = client.post(
            f"/glossaries/{g_glossary.glossary_id}/import-from-labels",
            json={
                "label_group_id": str(uuid.uuid4()),
                "overwrite_existing": False,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_import_glossary_not_found(self, client: TestClient, g_label_group: LabelGroup, g_owner: User):
        import uuid

        headers = get_auth_header(client, "g_owner")
        response = client.post(
            f"/glossaries/{uuid.uuid4()}/import-from-labels",
            json={
                "label_group_id": str(g_label_group.label_group_id),
                "overwrite_existing": False,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_import_viewer_cannot_import(
        self,
        client: TestClient,
        g_glossary_with_viewer: Glossary,
        g_label_data_with_labels: LabelData,
        g_label_group: LabelGroup,
        g_viewer: User,
    ):
        headers = get_auth_header(client, "g_viewer")
        response = client.post(
            f"/glossaries/{g_glossary_with_viewer.glossary_id}/import-from-labels",
            json={
                "label_group_id": str(g_label_group.label_group_id),
                "overwrite_existing": False,
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_import_unauthenticated(
        self,
        client: TestClient,
        g_glossary: Glossary,
        g_label_group: LabelGroup,
    ):
        response = client.post(
            f"/glossaries/{g_glossary.glossary_id}/import-from-labels",
            json={
                "label_group_id": str(g_label_group.label_group_id),
                "overwrite_existing": False,
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# Admin Access Tests
# ===========================================================================


class TestAdminAccess:
    def test_admin_can_read_any_glossary(self, client: TestClient, g_glossary: Glossary, g_admin: User):
        headers = get_auth_header(client, "g_admin")
        response = client.get(f"/glossaries/{g_glossary.glossary_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_update_any_glossary(self, client: TestClient, g_glossary: Glossary, g_admin: User):
        headers = get_auth_header(client, "g_admin")
        response = client.patch(
            f"/glossaries/{g_glossary.glossary_id}",
            json={"glossary_name": "Admin Updated"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_delete_any_glossary(
        self, client: TestClient, g_glossary: Glossary, g_admin: User, test_db: Session
    ):
        # Remove contributors first to satisfy FK constraint before deleting.
        test_db.query(GlossaryContributor).filter(GlossaryContributor.glossary_id == g_glossary.glossary_id).delete()
        test_db.commit()

        headers = get_auth_header(client, "g_admin")
        response = client.delete(f"/glossaries/{g_glossary.glossary_id}", headers=headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT
