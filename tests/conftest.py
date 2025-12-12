import pytest
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, List, Dict
from pathlib import Path
from arq import create_pool, ArqRedis
from arq.connections import RedisSettings
from pwdlib import PasswordHash

from src.models import Base
from src.languages.models import Language
from src.novels.models import Novel
from src.auth.models import User
from src.auth.constants import UserType


TEST_URL = os.getenv("TEST_URL")
if TEST_URL is None:
    raise EnvironmentError("TEST_URL environment variable not set for tests.")

engine = create_engine(TEST_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Creates a new database session for a test."""
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        connection.commit()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_languages(db_session : Session) -> Dict[str, Language]:
    # Create the standard languages needed for most tests
    en = Language(language_name="English", language_code="en")
    zh = Language(language_name="Chinese", language_code="zh")
    kr = Language(language_name="Korean", language_code="kr")
    jp = Language(language_name="Japanese", language_code="jp")
    db_session.add_all([en, zh, kr, jp])
    db_session.commit()
    db_session.refresh(en)
    db_session.refresh(zh)
    db_session.refresh(kr)
    db_session.refresh(jp)
    return {"en": en, "zh": zh, "kr": kr, "jp": jp}

@pytest.fixture 
def password_hash() -> PasswordHash:
    return PasswordHash.recommended()

@pytest.fixture
def sample_users(db_session : Session, password_hash : PasswordHash) -> List[User]:
    test_admin = User(user_name="admin", user_hashed_password = password_hash.hash('123'), user_type=UserType.ADMIN)
    test_user = User(user_name="user", user_hashed_password = password_hash.hash('456'), user_type=UserType.USER)
    db_session.add_all([test_admin, test_user])
    return [test_admin, test_user]

@pytest.fixture
def sample_novels(sample_languages : Dict[str, Language], db_session : Session) -> List[Novel]:
    # Create some sample novels
    novel0 = Novel(novel_title="Sample Novel 1", language_id=sample_languages['en'].language_id)
    novel1 = Novel(novel_title="Sample Novel 2", language_id=sample_languages['zh'].language_id)
    novel2 = Novel(novel_title="Sample Novel 3", language_id=sample_languages['kr'].language_id, novel_description="A description.", novel_author="An Author")
    novel3 = Novel(novel_title="Smample Novel 4", language_id=sample_languages['zh'].language_id, novel_description="Another description.", novel_author="Another Author")
    db_session.add_all([novel0, novel1, novel2, novel3])
    db_session.commit()
    db_session.refresh(novel0)

    db_session.refresh(novel1)
    db_session.refresh(novel2)
    db_session.refresh(novel3)
    return [novel0, novel1, novel2, novel3]

class ChapterLoader:
    """
    Class for a chapter loader. Callable class.
    """
    def __init__(self, base_path : Path):
        self.base_path = base_path
    
    def _load(self, subdir: str = "", recursive: bool = False) -> Generator[str, None, None]:
        target_dir = self.base_path / subdir
        
        if not target_dir.exists():
            raise FileNotFoundError(
                f"Test data directory not found: {target_dir}\n"
                f"Current base path: {self.base_path}"
            )        
        files = target_dir.rglob("*.txt") if recursive else target_dir.glob("*.txt")
        sorted_files = sorted(files, key=lambda p:p.name)
        for f in sorted_files:
            yield f.read_text(encoding='utf-8')
    
    def __call__(self, subdir: str = "", recursive: bool = False) -> Generator[str, None, None]:
        return self._load(subdir, recursive)


@pytest.fixture
def chapter_loader() -> ChapterLoader:
    """
    Returns a chapter loader callable that takes a pathname in the `test_data/chapters/` directory (e.g. if `chapters/chinese` contains `chapter_1.txt`, `chapter_2.txt`), then calling `chapter_loader().load("chinese")` should return a sequence of strings containing the content in `chapter_1.txt` and `chapter_2.txt`. Calling with the recursive flag will return the contents of all subdirectories as well (e.g. `chapter_loader().load("", recursive=True)` will also return chapters in `chapters/korean`, if that is a folder).
    """
    base_path = Path(__file__).parent / 'test_data' / 'chapters'
    return ChapterLoader(base_path)

@pytest.fixture
async def redis() -> ArqRedis:
    return await create_pool(RedisSettings(host='redis', port=6379))