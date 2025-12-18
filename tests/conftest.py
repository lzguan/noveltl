import pytest
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, List, Dict, Tuple, Protocol, cast
from pathlib import Path
from arq import create_pool, ArqRedis
from arq.connections import RedisSettings
from arq.worker import Worker
from pwdlib import PasswordHash
import json

# do not import schemas here
from src.models import Base
from src.languages.models import Language
from src.novels.models import Novel, RawChapter, RawChapterRevision
from src.autolabels.models import AutoLabel
from src.auth.models import User
from src.auth.constants import UserType
import src.autolabels.worker.tasks as worker_cfg
from src.autolabels.worker.worker import WorkerSettings
from src.labels.models import LabelGroup


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
    db_session.commit()
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

class DataLoader:
    """
    Class for a data loader. Callable class.
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
def chapter_loader() -> DataLoader:
    """
    Returns a chapter loader callable that takes a pathname in the `test_data/chapters/` directory (e.g. if `chapters/chinese` contains `chapter_1.txt`, `chapter_2.txt`), then calling `chapter_loader().load("chinese")` should return a generator of strings containing the content in `chapter_1.txt` and `chapter_2.txt`. 
    Calling with the recursive flag will return the contents of all subdirectories as well (e.g. `chapter_loader().load("", recursive=True)` will also return chapters in `chapters/korean`, if that is a folder).
    """
    base_path = Path(__file__).parent / 'test_data' / 'chapters'
    return DataLoader(base_path)

@pytest.fixture
def autolabel_loader() -> DataLoader:
    """
    Returns an autolabel loader callable that takes a pathname in the `test_data/autolabel/` directory (e.g. if `chapters/chinese` contains `chapter_1.json', `chapter_2.json`), then calling `autolabel_loader().load("chinese")` should return a generator of strings containing the content in `chapter_1.json` and `chapter_2.json`. 
    Calling with the recursive flag will return the contents of all subdirectories as well (e.g. `autolabel().load("", recursive=True)` will also return chapters in `chapters/korean`, if that is a folder).
    """
    base_path = Path(__file__).parent / 'test_data' / 'autolabels'
    return DataLoader(base_path)

@pytest.fixture
async def redis():
    pool = await create_pool(RedisSettings(host='redis', port=6379, database=1))
    yield pool
    await pool.aclose()


@pytest.fixture
async def worker_mock(monkeypatch : pytest.MonkeyPatch, redis : ArqRedis) -> Worker:
    # infer_autolabels uses worker_cfg.SessionLocal to configure its database connection
    monkeypatch.setattr(worker_cfg, 'SessionLocal', sessionmaker(create_engine(cast(str, TEST_URL))))

    return Worker(
        functions=WorkerSettings.functions,
        redis_pool=redis,
        on_startup=WorkerSettings.on_startup,
        burst=True,
        poll_delay=0
    )


@pytest.fixture
def chinese_xianxia_small_test_novel(sample_languages : Dict[str, Language], db_session : Session) -> Novel:
    test_novel = Novel(novel_title="Test", language_id=sample_languages['zh'].language_id)
    db_session.add(test_novel)
    db_session.commit()
    return test_novel

class Loader(Protocol):
    def __call__(self, pathname : str, recursive : bool = False) -> Generator[str, None, None]:
        ...

@pytest.fixture
def chinese_xianxia_small_test_label_group(sample_users : List[User], chinese_xianxia_small_test_novel : Novel, db_session : Session) -> LabelGroup:
    """
    Fixture for a single label group using sample_users, with sample_users[0] being the owning user
    """
    label_group = LabelGroup(label_group_name="small test", user_id=sample_users[0].user_id, novel_id=chinese_xianxia_small_test_novel.novel_id)
    db_session.add(label_group)
    db_session.commit()
    return label_group

def test_chinese_xianxia_small_test_label_group(chinese_xianxia_small_test_label_group):
    pass

@pytest.fixture
def chinese_xianxia_small_test_chapters(
    chinese_xianxia_small_test_novel : Novel, 
    chapter_loader : Loader, 
    db_session : Session
) -> List[Tuple[RawChapter, RawChapterRevision]]:
    texts = chapter_loader('chinese/chinese_xianxia/small_test')
    out : List[Tuple[RawChapter, RawChapterRevision]] = []
    i = 0
    for text in texts:
        chapter = RawChapter(raw_chapter_num=i, novel_id=chinese_xianxia_small_test_novel.novel_id)
        db_session.add(chapter)
        db_session.commit()
        revision = RawChapterRevision(
            raw_chapter_revision_text=text,
            raw_chapter_revision_title=f"chapter {i}",
            raw_chapter_revision_is_primary=True,
            raw_chapter_revision_is_public=True,
            raw_chapter_revision_is_final=True, 
            raw_chapter_id=chapter.raw_chapter_id
        )
        db_session.add(revision)
        db_session.commit() # can optimize this
        out.append((chapter, revision))
        i = i + 1
    return out

@pytest.fixture
def chinese_xianxia_small_test_default_params_cluener() -> Dict:
    return  {"chunk_size": 500, "separators": {"\n": 1, "!": 2, ",": 3, ".": 2, ":": 3, ";": 3, "?": 2, "\u3002": 2, "\uff01": 2, "\uff0c": 3, "\uff1a": 3, "\uff1b": 3, "\uff1f": 2}, "force_chunk": False}

@pytest.fixture
def chinese_xianxia_small_test_autolabels_cluener(
    db_session : Session,
    chinese_xianxia_small_test_chapters : List[Tuple[RawChapter, RawChapterRevision]],
    autolabel_loader : Loader
) -> List[AutoLabel]:
    autolabels_gen = (json.loads(l) for l in autolabel_loader('chinese/chinese_xianxia/small_test/cluener'))
    out = []
    i = 0
    for autolabel in autolabels_gen:
        a = AutoLabel(**autolabel, raw_chapter_revision_id=chinese_xianxia_small_test_chapters[i][1].raw_chapter_revision_id)
        db_session.add(a)
        db_session.commit() # can optimize this
        i = i + 1
        out.append(a)
    return out