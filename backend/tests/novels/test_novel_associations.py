"""
Tests for novel association endpoints.

Tests cover:
- Create association (POST /novel-associations)
- Duplicate association detection (409)
- Unauthenticated access (401)
- Insufficient permissions (401 - not owner/editor of source novel)
- Query associations (GET /novel-associations?source-novel-id=X)
- Query empty associations
- Delete association (DELETE /novel-associations/{id})
- Delete not found (404)
- Delete without permission (404)
- Admin bypasses contributor check
"""

from typing import Any, Protocol

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.novels.constants import AssociationType, NovelType, Role, Visibility
from src.novels.models import Contributor, Novel, NovelAssociation
from src.languages.models import Language


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...
    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def na_language(test_db: Session) -> Language:
    lang = Language(language_name="Chinese", language_code="zh")
    lang_en = Language(language_name="English", language_code="en")
    test_db.add_all([lang, lang_en])
    test_db.commit()
    return lang


@pytest.fixture
def na_owner(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="na_owner", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def na_editor(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="na_editor", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def na_outsider(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="na_outsider", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def na_admin(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="na_admin", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.ADMIN)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def na_source_novel(test_db: Session, na_language: Language, na_owner: User) -> Novel:
    novel = Novel(
        novel_title="Source Novel",
        language_code=na_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=na_owner.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def na_source_novel_with_editor(test_db: Session, na_source_novel: Novel, na_editor: User) -> Novel:
    test_db.add(
        Contributor(novel_id=na_source_novel.novel_id, user_id=na_editor.user_id, contributor_role=Role.EDITOR)
    )
    test_db.commit()
    return na_source_novel


@pytest.fixture
def na_target_novel(test_db: Session, na_language: Language, na_owner: User) -> Novel:
    novel = Novel(
        novel_title="Target Novel",
        language_code="en",
        novel_type=NovelType.TRANSLATION,
        novel_visibility=Visibility.PUBLIC,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=na_owner.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def na_association(test_db: Session, na_source_novel: Novel, na_target_novel: Novel) -> NovelAssociation:
    assoc = NovelAssociation(
        source_novel_id=na_source_novel.novel_id,
        target_novel_id=na_target_novel.novel_id,
        association_type=AssociationType.TRANSLATION,
    )
    test_db.add(assoc)
    test_db.commit()
    return assoc


def get_auth_header(client: TestClient, username: str, password: str = "pass") -> dict[str, str]:
    resp = client.post("/token", data={"username": username, "password": password})
    assert resp.status_code == status.HTTP_200_OK
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Tests: Create Association
# ===========================================================================


class TestCreateNovelAssociation:
    def test_create_association_success(
        self,
        client: TestClient,
        na_owner: User,
        na_source_novel: Novel,
        na_target_novel: Novel,
    ):
        headers = get_auth_header(client, "na_owner")
        response = client.post(
            "/novel-associations",
            json={
                "source_novel_id": str(na_source_novel.novel_id),
                "target_novel_id": str(na_target_novel.novel_id),
                "association_type": "translation",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "association_id" in data
        assert data["source_novel_id"] == str(na_source_novel.novel_id)
        assert data["target_novel_id"] == str(na_target_novel.novel_id)
        assert data["association_type"] == "translation"

    def test_create_association_duplicate_returns_409(
        self,
        client: TestClient,
        na_owner: User,
        na_association: NovelAssociation,
        na_source_novel: Novel,
        na_target_novel: Novel,
    ):
        headers = get_auth_header(client, "na_owner")
        response = client.post(
            "/novel-associations",
            json={
                "source_novel_id": str(na_source_novel.novel_id),
                "target_novel_id": str(na_target_novel.novel_id),
                "association_type": "translation",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_association_unauthenticated_returns_401(
        self,
        client: TestClient,
        na_source_novel: Novel,
        na_target_novel: Novel,
    ):
        response = client.post(
            "/novel-associations",
            json={
                "source_novel_id": str(na_source_novel.novel_id),
                "target_novel_id": str(na_target_novel.novel_id),
                "association_type": "translation",
            },
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_association_outsider_returns_401(
        self,
        client: TestClient,
        na_outsider: User,
        na_source_novel: Novel,
        na_target_novel: Novel,
    ):
        headers = get_auth_header(client, "na_outsider")
        response = client.post(
            "/novel-associations",
            json={
                "source_novel_id": str(na_source_novel.novel_id),
                "target_novel_id": str(na_target_novel.novel_id),
                "association_type": "translation",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_association_editor_succeeds(
        self,
        client: TestClient,
        na_editor: User,
        na_source_novel_with_editor: Novel,
        na_target_novel: Novel,
    ):
        headers = get_auth_header(client, "na_editor")
        response = client.post(
            "/novel-associations",
            json={
                "source_novel_id": str(na_source_novel_with_editor.novel_id),
                "target_novel_id": str(na_target_novel.novel_id),
                "association_type": "translation",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_association_admin_succeeds(
        self,
        client: TestClient,
        na_admin: User,
        na_source_novel: Novel,
        na_target_novel: Novel,
    ):
        headers = get_auth_header(client, "na_admin")
        response = client.post(
            "/novel-associations",
            json={
                "source_novel_id": str(na_source_novel.novel_id),
                "target_novel_id": str(na_target_novel.novel_id),
                "association_type": "translation",
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_201_CREATED


# ===========================================================================
# Tests: Query Associations
# ===========================================================================


class TestQueryNovelAssociations:
    def test_query_associations_returns_list(
        self,
        client: TestClient,
        na_association: NovelAssociation,
        na_source_novel: Novel,
    ):
        response = client.get(f"/novel-associations?source-novel-id={na_source_novel.novel_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["association_id"] == str(na_association.association_id)
        assert data[0]["source_novel_id"] == str(na_source_novel.novel_id)
        assert data[0]["association_type"] == "translation"

    def test_query_associations_empty_list(
        self,
        client: TestClient,
        na_source_novel: Novel,
    ):
        response = client.get(f"/novel-associations?source-novel-id={na_source_novel.novel_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == []

    def test_query_associations_novel_not_found(self, client: TestClient):
        import uuid

        response = client.get(f"/novel-associations?source-novel-id={uuid.uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# Tests: Delete Association
# ===========================================================================


class TestDeleteNovelAssociation:
    def test_delete_association_success(
        self,
        client: TestClient,
        na_owner: User,
        na_association: NovelAssociation,
    ):
        headers = get_auth_header(client, "na_owner")
        response = client.delete(
            f"/novel-associations/{na_association.association_id}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_association_not_found_returns_404(
        self,
        client: TestClient,
        na_owner: User,
    ):
        import uuid

        headers = get_auth_header(client, "na_owner")
        response = client.delete(
            f"/novel-associations/{uuid.uuid4()}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_association_without_permission_returns_404(
        self,
        client: TestClient,
        na_outsider: User,
        na_association: NovelAssociation,
    ):
        headers = get_auth_header(client, "na_outsider")
        response = client.delete(
            f"/novel-associations/{na_association.association_id}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_association_unauthenticated_returns_401(
        self,
        client: TestClient,
        na_association: NovelAssociation,
    ):
        response = client.delete(f"/novel-associations/{na_association.association_id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_association_admin_succeeds(
        self,
        client: TestClient,
        na_admin: User,
        na_association: NovelAssociation,
    ):
        headers = get_auth_header(client, "na_admin")
        response = client.delete(
            f"/novel-associations/{na_association.association_id}",
            headers=headers,
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
