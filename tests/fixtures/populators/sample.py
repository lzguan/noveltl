import pytest

from sqlalchemy.orm import Session
from typing import Dict, List, Protocol

from src.languages.models import Language
from src.auth.constants import UserType
from src.auth.models import User
from src.novels.models import Novel

class Hash(Protocol):
    def hash(self, password : str | bytes, *args, **kwargs) -> str:
        ...

    def verify(self, password : str | bytes, hash : str | bytes) -> bool:
        ...

@pytest.fixture
def sample_languages(test_db : Session) -> Dict[str, Language]:
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
def sample_users(test_db : Session, recommended_hash : Hash) -> List[User]:
    test_admin = User(user_name="admin", user_hashed_password = recommended_hash.hash('123'), user_type=UserType.ADMIN)
    test_user = User(user_name="user", user_hashed_password = recommended_hash.hash('456'), user_type=UserType.USER)
    test_db.add_all([test_admin, test_user])
    test_db.commit()
    return [test_admin, test_user]

@pytest.fixture
def sample_novels(sample_languages : Dict[str, Language], test_db : Session) -> List[Novel]:
    # Create some sample novels
    novel0 = Novel(novel_title="Sample Novel 1", language_id=sample_languages['en'].language_id)
    novel1 = Novel(novel_title="Sample Novel 2", language_id=sample_languages['zh'].language_id)
    novel2 = Novel(novel_title="Sample Novel 3", language_id=sample_languages['kr'].language_id, novel_description="A description.", novel_author="An Author")
    novel3 = Novel(novel_title="Smample Novel 4", language_id=sample_languages['zh'].language_id, novel_description="Another description.", novel_author="Another Author")
    test_db.add_all([novel0, novel1, novel2, novel3])
    test_db.commit()
    test_db.refresh(novel0)

    test_db.refresh(novel1)
    test_db.refresh(novel2)
    test_db.refresh(novel3)
    return [novel0, novel1, novel2, novel3]