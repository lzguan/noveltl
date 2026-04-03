from typing import Any, Protocol

import pytest
from sqlalchemy.orm import Session

from src.auth.constants import UserType
from src.auth.models import User
from src.languages.models import Language
from src.novels.constants import NovelType, Role, Visibility
from src.novels.models import Contributor, Novel


@pytest.fixture
def p1_language(test_db: Session) -> Language:
    zh = Language(language_name="Chinese", language_code="zh")
    test_db.add(zh)
    test_db.commit()
    return zh


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...

    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


@pytest.fixture
def p1_user_1(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="tyrone", user_hashed_password=no_hash.hash("abc"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def p1_user_2(test_db: Session, no_hash: Hash) -> User:
    user = User(user_name="speed", user_hashed_password=no_hash.hash("def"), user_type=UserType.USER)
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def p1_admin(test_db: Session, no_hash: Hash) -> User:
    admin = User(user_name="admin", user_hashed_password=no_hash.hash("adminpass"), user_type=UserType.ADMIN)
    test_db.add(admin)
    test_db.commit()
    return admin


@pytest.fixture
def p1_novel_public_tyrone(p1_language: Language, test_db: Session, p1_user_1: User) -> Novel:
    test_novel = Novel(
        novel_title="pt",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_1.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novel_public_speed(p1_language: Language, test_db: Session, p1_user_2: User) -> Novel:
    test_novel = Novel(
        novel_title="ps",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PUBLIC,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_2.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novel_unlisted_tyrone(p1_language: Language, test_db: Session, p1_user_1: User) -> Novel:
    test_novel = Novel(
        novel_title="ut",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.UNLISTED,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_1.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novel_unlisted_speed(p1_language: Language, test_db: Session, p1_user_2: User) -> Novel:
    test_novel = Novel(
        novel_title="us",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.UNLISTED,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_2.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novel_restricted_tyrone(p1_language: Language, test_db: Session, p1_user_1: User) -> Novel:
    test_novel = Novel(
        novel_title="rt",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.RESTRICTED,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_1.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novel_restricted_speed(p1_language: Language, test_db: Session, p1_user_2: User) -> Novel:
    test_novel = Novel(
        novel_title="rs",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.RESTRICTED,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_2.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novel_private_tyrone(p1_language: Language, test_db: Session, p1_user_1: User) -> Novel:
    test_novel = Novel(
        novel_title="prt",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PRIVATE,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_1.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novel_private_speed(p1_language: Language, test_db: Session, p1_user_2: User) -> Novel:
    test_novel = Novel(
        novel_title="prs",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PRIVATE,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_2.user_id, contributor_role=Role.OWNER))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novel_owner_editor(p1_language: Language, test_db: Session, p1_user_1: User, p1_user_2: User) -> Novel:
    test_novel = Novel(
        novel_title="oe",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PRIVATE,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_1.user_id, contributor_role=Role.OWNER))
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_2.user_id, contributor_role=Role.EDITOR))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novel_owner_viewer(p1_language: Language, test_db: Session, p1_user_1: User, p1_user_2: User) -> Novel:
    test_novel = Novel(
        novel_title="ov",
        language_code=p1_language.language_code,
        novel_type=NovelType.ORIGINAL,
        novel_visibility=Visibility.PRIVATE,
    )
    test_db.add(test_novel)
    test_db.commit()
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_1.user_id, contributor_role=Role.OWNER))
    test_db.add(Contributor(novel_id=test_novel.novel_id, user_id=p1_user_2.user_id, contributor_role=Role.VIEWER))
    test_db.commit()
    return test_novel


@pytest.fixture
def p1_novels(
    p1_novel_public_tyrone: Novel,
    p1_novel_public_speed: Novel,
    p1_novel_unlisted_tyrone: Novel,
    p1_novel_unlisted_speed: Novel,
    p1_novel_restricted_tyrone: Novel,
    p1_novel_restricted_speed: Novel,
    p1_novel_private_tyrone: Novel,
    p1_novel_private_speed: Novel,
    p1_novel_owner_editor: Novel,
    p1_novel_owner_viewer: Novel,
) -> dict[str, Novel]:
    return {
        "put": p1_novel_public_tyrone,
        "pus": p1_novel_public_speed,
        "ut": p1_novel_unlisted_tyrone,
        "us": p1_novel_unlisted_speed,
        "rt": p1_novel_restricted_tyrone,
        "rs": p1_novel_restricted_speed,
        "prt": p1_novel_private_tyrone,
        "prs": p1_novel_private_speed,
        "oe": p1_novel_owner_editor,
        "ov": p1_novel_owner_viewer,
    }
