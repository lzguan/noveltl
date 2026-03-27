from typing import Any, Protocol

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.labels.constants import LabelRole
from src.labels.models import Label, LabelContributor, LabelData, LabelGroup
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Chapter, Contributor, Novel, Revision, RevisionText


class Hash(Protocol):
    def hash(self, password : str | bytes, *args : Any, **kwargs : Any) -> str:
        ...

    def verify(self, password : str | bytes, hash : str | bytes) -> bool:
        ...

@pytest.fixture
def sample_languages(test_db : Session) -> dict[str, Language]:
    # Create the standard languages needed for most tests
    en = Language(language_name="English", language_code="en")
    zh = Language(language_name="Chinese", language_code="zh")
    kr = Language(language_name="Korean", language_code="kr")
    jp = Language(language_name="Japanese", language_code="jp")
    test_db.add_all([en, zh, kr, jp])
    test_db.commit()
    test_db.refresh(en)
    test_db.refresh(zh)
    test_db.refresh(kr)
    test_db.refresh(jp)
    return {"en": en, "zh": zh, "kr": kr, "jp": jp}

@pytest.fixture
def sample_users(test_db : Session, recommended_hash : Hash) -> list[User]:
    test_admin = User(user_name="admin", user_hashed_password = recommended_hash.hash('123'), user_type=UserType.ADMIN)
    test_user = User(user_name="user", user_hashed_password = recommended_hash.hash('456'), user_type=UserType.USER)
    test_db.add_all([test_admin, test_user])
    test_db.commit()
    return [test_admin, test_user]

@pytest.fixture
def sample_novels(sample_languages : dict[str, Language], test_db : Session) -> list[Novel]:
    # Create some sample novels
    novel0 = Novel(novel_title="Sample Novel 1", language_code=sample_languages['en'].language_code, novel_type=NovelType.ORIGINAL, novel_visibility=Visibility.PUBLIC)
    novel1 = Novel(novel_title="Sample Novel 2", language_code=sample_languages['zh'].language_code, novel_type=NovelType.ORIGINAL, novel_visibility=Visibility.PUBLIC)
    novel2 = Novel(novel_title="Sample Novel 3", language_code=sample_languages['kr'].language_code, novel_description="A description.", novel_author="An Author", novel_type=NovelType.ORIGINAL, novel_visibility=Visibility.PUBLIC)
    novel3 = Novel(novel_title="Smample Novel 4", language_code=sample_languages['zh'].language_code, novel_description="Another description.", novel_author="Another Author", novel_type=NovelType.ORIGINAL, novel_visibility=Visibility.PUBLIC)
    test_db.add_all([novel0, novel1, novel2, novel3])
    test_db.commit()
    test_db.refresh(novel0)

    test_db.refresh(novel1)
    test_db.refresh(novel2)
    test_db.refresh(novel3)
    return [novel0, novel1, novel2, novel3]

@pytest.fixture
def sample_contributors(test_db: Session, sample_novels: list[Novel], sample_users: list[User]) -> list[Contributor]:
    # Assign the regular user as the OWNER of Novel 1 and EDITOR of Novel 2
    c1 = Contributor(novel_id=sample_novels[1].novel_id, user_id=sample_users[1].user_id, contributor_role=Role.OWNER)
    c2 = Contributor(novel_id=sample_novels[2].novel_id, user_id=sample_users[1].user_id, contributor_role=Role.EDITOR)

    test_db.add_all([c1, c2])
    test_db.commit()
    return [c1, c2]

@pytest.fixture
def sample_chapters(test_db: Session, sample_novels: list[Novel]) -> list[Chapter]:
    # Add chapters to Novel 1
    ch1 = Chapter(novel_id=sample_novels[0].novel_id, chapter_num=1)
    ch2 = Chapter(novel_id=sample_novels[0].novel_id, chapter_num=2)

    test_db.add_all([ch1, ch2])
    test_db.commit()
    test_db.refresh(ch1)
    test_db.refresh(ch2)
    return [ch1, ch2]

@pytest.fixture
def sample_revisions(test_db: Session, sample_chapters: list[Chapter]) -> list[tuple[Revision, RevisionText]]:
    # Create revisions for Chapter 1
    # We use specific text here so we can create a valid Label for it later.
    rev1 = Revision(
        chapter_id=sample_chapters[0].chapter_id,
        revision_title="Chapter 1: The Beginning",
        revision_is_primary=True,
        revision_is_public=True,
    )
    # Create a non-primary, non-public draft
    rev2 = Revision(
        chapter_id=sample_chapters[0].chapter_id,
        revision_title="Chapter 1: Draft",
        revision_is_primary=False,
        revision_is_public=False,
    )

    test_db.add_all([rev1, rev2])
    test_db.commit()

    rt1 = RevisionText(revision_id=rev1.revision_id, revision_text_content="Alice went to the market.", revision_text_version=1)
    rt2 = RevisionText(revision_id=rev2.revision_id, revision_text_content="This is a draft text.", revision_text_version=1)
    test_db.add_all([rt1, rt2])
    test_db.commit()

    return [(rev1, rt1), (rev2, rt2)]

@pytest.fixture
def sample_label_groups(test_db: Session, sample_novels: list[Novel], sample_users: list[User]) -> list[LabelGroup]:
    # Create a label group for Novel 1 owned by the Admin
    lg1 = LabelGroup(
        label_group_name="Official Labels",
        novel_id=sample_novels[0].novel_id,
    )
    test_db.add(lg1)
    test_db.commit()
    test_db.refresh(lg1)
    return [lg1]

@pytest.fixture
def sample_label_contributors(test_db: Session, sample_label_groups: list[LabelGroup], sample_users: list[User]) -> list[LabelContributor]:
    # Assign Admin as OWNER of the label group
    lc1 = LabelContributor(
        label_group_id=sample_label_groups[0].label_group_id,
        user_id=sample_users[0].user_id,
        label_contributor_role=LabelRole.OWNER
    )
    test_db.add(lc1)
    test_db.commit()
    return [lc1]

@pytest.fixture
def sample_label_datas(test_db: Session, sample_label_groups: list[LabelGroup], sample_revisions: list[tuple[Revision, RevisionText]]) -> list[LabelData]:
    # Link the Label Data to the Primary Revision of Chapter 1
    _, rt1 = sample_revisions[0]
    ld1 = LabelData(
        label_group_id=sample_label_groups[0].label_group_id,
        revision_text_id=rt1.revision_text_id
    )
    test_db.add(ld1)
    test_db.commit()
    test_db.refresh(ld1)
    return [ld1]

@pytest.fixture
def sample_labels(test_db: Session, sample_label_datas: list[LabelData]) -> list[Label]:
    # Add a label to the Label Data
    # Text: "Alice went to the market."
    #        012345
    # Word: "Alice" (indices 0-5)
    l1 = Label(
        label_data_id=sample_label_datas[0].label_data_id,
        label_entity_group="PER",
        label_word="Alice",
        label_start=0,
        label_end=5,
        label_score=1.0,
        label_dirty=False
    )
    test_db.add(l1)
    test_db.commit()
    return [l1]
