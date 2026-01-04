import pytest
import os
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from pathlib import Path
from arq import create_pool, ArqRedis
from arq.connections import RedisSettings
from arq.worker import Worker

from src.models import Base
import src.autolabels.worker.tasks as worker_cfg
from src.autolabels.worker.worker import WorkerSettings

pytest_plugins = [
    "tests.fixtures.populators.sample",
    "tests.fixtures.populators.chinese_xianxia_small_test",
    "tests.fixtures.populators.permissions_one",
    "tests.fixtures.password_hash"
]

@pytest.fixture
def test_url() -> str:
    ret = os.getenv("TEST_URL")
    if ret is None:
        raise EnvironmentError("TEST_URL environment variable not set for tests.")
    return ret

@pytest.fixture
def test_engine(test_url : str) -> Engine:
    engine = create_engine(test_url)
    return engine

@pytest.fixture
def testing_session_local(test_engine : Engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def test_db(test_engine : Engine, testing_session_local : sessionmaker) -> Generator[Session, None, None]:
    """Creates a new database session for a test."""
    with test_engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        connection.commit()

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
async def redis():
    pool = await create_pool(RedisSettings(host='redis', port=6379, database=1))
    yield pool
    await pool.aclose()

@pytest.fixture
async def worker_mock(test_url : str, monkeypatch : pytest.MonkeyPatch, redis : ArqRedis) -> Worker:
    # infer_autolabels uses worker_cfg.SessionLocal to configure its database connection
    monkeypatch.setattr(worker_cfg, 'SessionLocal', sessionmaker(create_engine(test_url)))

    return Worker(
        functions=WorkerSettings.functions,
        redis_pool=redis,
        on_startup=WorkerSettings.on_startup,
        burst=True,
        poll_delay=0
    )

class DataLoader:
    """
    Class for a data loader. Callable class.
    """
    def __init__(self, base_path : Path, pattern : str):
        self.base_path = base_path
        self.pattern = pattern
    
    def _load(self, subdir: str = "", recursive: bool = False) -> Generator[str, None, None]:
        target_dir = self.base_path / subdir
        
        if not target_dir.exists():
            raise FileNotFoundError(
                f"Test data directory not found: {target_dir}\n"
                f"Current base path: {self.base_path}"
            )        
        files = target_dir.rglob(self.pattern) if recursive else target_dir.glob(self.pattern)
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
    return DataLoader(base_path, "*.txt")

@pytest.fixture
def autolabel_loader() -> DataLoader:
    """
    Returns an autolabel loader callable that takes a pathname in the `test_data/autolabel/` directory (e.g. if `chapters/chinese` contains `chapter_1.json', `chapter_2.json`), then calling `autolabel_loader().load("chinese")` should return a generator of strings containing the content in `chapter_1.json` and `chapter_2.json`. 
    Calling with the recursive flag will return the contents of all subdirectories as well (e.g. `autolabel().load("", recursive=True)` will also return chapters in `autolabels/korean`, if that is a folder).
    """
    base_path = Path(__file__).parent / 'test_data' / 'autolabels'
    return DataLoader(base_path, "*.json")