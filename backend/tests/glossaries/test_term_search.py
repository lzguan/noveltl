"""
Tests for the term search endpoint.

Tests cover:
- String mode basic: term found in chapter text → positions returned
- String mode multiple chapters: term in multiple chapters → ordered by chapter_num
- String mode no match: term not in any chapter → empty occurrences
- String mode multiple positions: term appears multiple times in one chapter
- Label mode: labels matching source_term found → positions from labels
- Label mode requires label_group_id: mode=label without label_group_id → 400
- Entry not found: nonexistent entry → 404
- Permissions: user without novel access can't search → 404
"""

import uuid
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
def ts_language(test_db: Session) -> Language:
    lang_zh = Language(language_name="Chinese", language_code="zh")
    lang_en = Language(language_name="English", language_code="en")
    test_db.add_all([lang_zh, lang_en])
    test_db.commit()
    return lang_zh


@pytest.fixture
def ts_owner(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="ts_owner", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def ts_outsider(test_db: Session, recommended_hash: Hash) -> User:
    user = User(user_name="ts_outsider", user_hashed_password=recommended_hash.hash("pass"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def ts_novel(test_db: Session, ts_language: Language, ts_owner: User) -> Novel:
    novel = Novel(
        novel_title="Search Novel",
        language_code=ts_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PRIVATE,
    )
    test_db.add(novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=novel.novel_id, user_id=ts_owner.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return novel


@pytest.fixture
def ts_glossary(test_db: Session, ts_novel: Novel, ts_owner: User) -> Glossary:
    glossary = Glossary(
        glossary_name="Search Glossary",
        novel_id=ts_novel.novel_id,
        source_language_code="zh",
        target_language_code="en",
    )
    test_db.add(glossary)
    test_db.commit()
    test_db.add(
        GlossaryContributor(
            glossary_id=glossary.glossary_id,
            user_id=ts_owner.user_id,
            glossary_contributor_role=GlossaryRole.OWNER,
        )
    )
    test_db.commit()
    return glossary


@pytest.fixture
def ts_entry(test_db: Session, ts_glossary: Glossary) -> GlossaryEntry:
    entry = GlossaryEntry(
        glossary_id=ts_glossary.glossary_id,
        source_term="龙",
        translated_term="Dragon",
        entity_type="MISC",
    )
    test_db.add(entry)
    test_db.commit()
    return entry


def make_chapter_with_revision(
    test_db: Session,
    novel: Novel,
    chapter_num: int,
    text_content: str,
) -> tuple[Chapter, Revision, RevisionText]:
    """Helper to create a chapter with a primary revision and revision text."""
    chapter = Chapter(chapter_num=chapter_num, novel_id=novel.novel_id)
    test_db.add(chapter)
    test_db.commit()
    revision = Revision(
        chapter_id=chapter.chapter_id,
        revision_title=f"Chapter {chapter_num}",
        revision_is_primary=True,
        revision_is_public=True,
    )
    test_db.add(revision)
    test_db.commit()
    rt = RevisionText(
        revision_id=revision.revision_id,
        revision_text_content=text_content,
        revision_text_version=1,
    )
    test_db.add(rt)
    test_db.commit()
    return chapter, revision, rt


def get_auth_header(client: TestClient, username: str, password: str = "pass") -> dict[str, str]:
    resp = client.post("/token", data={"username": username, "password": password})
    assert resp.status_code == status.HTTP_200_OK
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Tests: String Mode
# ===========================================================================


class TestStringModeSearch:
    def test_string_mode_basic_finds_term(
        self,
        client: TestClient,
        test_db: Session,
        ts_owner: User,
        ts_novel: Novel,
        ts_entry: GlossaryEntry,
    ):
        """Term appears once in chapter text — one occurrence with one position."""
        make_chapter_with_revision(test_db, ts_novel, 1, "The 龙 roams the mountains.")

        headers = get_auth_header(client, "ts_owner")
        response = client.post(
            f"/glossary-entries/{ts_entry.glossary_entry_id}/search-occurrences",
            json={"mode": "string"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["occurrences"]) == 1
        occ = data["occurrences"][0]
        assert occ["chapter_num"] == 1
        assert len(occ["positions"]) == 1
        pos = occ["positions"][0]
        # "The 龙 roams..." → 龙 is at index 4, end 5
        assert pos["start"] == 4
        assert pos["end"] == 5

    def test_string_mode_multiple_chapters_ordered_by_chapter_num(
        self,
        client: TestClient,
        test_db: Session,
        ts_owner: User,
        ts_novel: Novel,
        ts_entry: GlossaryEntry,
    ):
        """Term in multiple chapters — results ordered by chapter_num ascending."""
        make_chapter_with_revision(test_db, ts_novel, 2, "Chapter two mentions 龙 here.")
        make_chapter_with_revision(test_db, ts_novel, 1, "Chapter one has 龙 too.")

        headers = get_auth_header(client, "ts_owner")
        response = client.post(
            f"/glossary-entries/{ts_entry.glossary_entry_id}/search-occurrences",
            json={"mode": "string"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["occurrences"]) == 2
        assert data["occurrences"][0]["chapter_num"] == 1
        assert data["occurrences"][1]["chapter_num"] == 2

    def test_string_mode_no_match_returns_empty(
        self,
        client: TestClient,
        test_db: Session,
        ts_owner: User,
        ts_novel: Novel,
        ts_entry: GlossaryEntry,
    ):
        """Term not found in any chapter — empty occurrences, total_count 0."""
        make_chapter_with_revision(test_db, ts_novel, 1, "This text has no matching term.")

        headers = get_auth_header(client, "ts_owner")
        response = client.post(
            f"/glossary-entries/{ts_entry.glossary_entry_id}/search-occurrences",
            json={"mode": "string"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 0
        assert data["occurrences"] == []

    def test_string_mode_multiple_positions_same_chapter(
        self,
        client: TestClient,
        test_db: Session,
        ts_owner: User,
        ts_novel: Novel,
        ts_entry: GlossaryEntry,
    ):
        """Term appears multiple times in one chapter — multiple positions reported."""
        make_chapter_with_revision(test_db, ts_novel, 1, "龙 and 龙 and 龙.")

        headers = get_auth_header(client, "ts_owner")
        response = client.post(
            f"/glossary-entries/{ts_entry.glossary_entry_id}/search-occurrences",
            json={"mode": "string"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 3
        assert len(data["occurrences"]) == 1
        assert len(data["occurrences"][0]["positions"]) == 3


# ===========================================================================
# Tests: Label Mode
# ===========================================================================


class TestLabelModeSearch:
    def _make_label_group_with_labels(
        self,
        test_db: Session,
        ts_novel: Novel,
        ts_owner: User,
        term: str,
        label_start: int,
        label_end: int,
        chapter_num: int = 1,
        text_content: str = "Some text content.",
    ) -> tuple[LabelGroup, LabelData]:
        _chapter, _revision, rt = make_chapter_with_revision(test_db, ts_novel, chapter_num, text_content)
        lg = LabelGroup(label_group_name="Test Labels", novel_id=ts_novel.novel_id)
        test_db.add(lg)
        test_db.commit()
        test_db.add(
            LabelContributor(
                label_group_id=lg.label_group_id,
                user_id=ts_owner.user_id,
                label_contributor_role=LabelRole.OWNER,
            )
        )
        test_db.commit()
        ld = LabelData(label_group_id=lg.label_group_id, revision_text_id=rt.revision_text_id)
        test_db.add(ld)
        test_db.commit()
        label = Label(
            label_data_id=ld.label_data_id,
            label_word=term,
            label_start=label_start,
            label_end=label_end,
            label_entity_group="MISC",
            label_score=0.95,
            label_dirty=False,
        )
        test_db.add(label)
        test_db.commit()
        return lg, ld

    def test_label_mode_finds_matching_labels(
        self,
        client: TestClient,
        test_db: Session,
        ts_owner: User,
        ts_novel: Novel,
        ts_entry: GlossaryEntry,
    ):
        """Label with matching term word → position reported."""
        lg, _ld = self._make_label_group_with_labels(
            test_db, ts_novel, ts_owner, term="龙", label_start=4, label_end=5, text_content="The 龙 roams."
        )

        headers = get_auth_header(client, "ts_owner")
        response = client.post(
            f"/glossary-entries/{ts_entry.glossary_entry_id}/search-occurrences",
            json={"mode": "label", "label_group_id": str(lg.label_group_id)},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["occurrences"]) == 1
        assert data["occurrences"][0]["positions"][0]["start"] == 4
        assert data["occurrences"][0]["positions"][0]["end"] == 5

    def test_label_mode_without_label_group_id_returns_400(
        self,
        client: TestClient,
        ts_owner: User,
        ts_entry: GlossaryEntry,
    ):
        """Label mode without label_group_id → 400 Bad Request."""
        headers = get_auth_header(client, "ts_owner")
        response = client.post(
            f"/glossary-entries/{ts_entry.glossary_entry_id}/search-occurrences",
            json={"mode": "label"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ===========================================================================
# Tests: Error Cases and Permissions
# ===========================================================================


class TestTermSearchErrorsAndPermissions:
    def test_entry_not_found_returns_404(
        self,
        client: TestClient,
        ts_owner: User,
    ):
        """Nonexistent glossary entry → 404."""
        headers = get_auth_header(client, "ts_owner")
        response = client.post(
            f"/glossary-entries/{uuid.uuid4()}/search-occurrences",
            json={"mode": "string"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_user_without_novel_access_cannot_search(
        self,
        client: TestClient,
        test_db: Session,
        ts_outsider: User,
        ts_novel: Novel,
        ts_entry: GlossaryEntry,
    ):
        """User without access to the private novel cannot see the glossary entry → 404."""
        make_chapter_with_revision(test_db, ts_novel, 1, "龙 appears here.")

        headers = get_auth_header(client, "ts_outsider")
        response = client.post(
            f"/glossary-entries/{ts_entry.glossary_entry_id}/search-occurrences",
            json={"mode": "string"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_guest_cannot_search_private_novel(
        self,
        client: TestClient,
        test_db: Session,
        ts_novel: Novel,
        ts_entry: GlossaryEntry,
    ):
        """Unauthenticated request on private novel → 404."""
        make_chapter_with_revision(test_db, ts_novel, 1, "龙 text here.")

        response = client.post(
            f"/glossary-entries/{ts_entry.glossary_entry_id}/search-occurrences",
            json={"mode": "string"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
