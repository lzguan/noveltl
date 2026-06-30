import json
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import redis as r
from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from arq.worker import Worker
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.autolabels.worker.worker import WorkerSettings
from src.database import get_db
from src.main import app
from src.models import Base
from src.redis_conn import get_redis_for_app


class FakeTTLCacheSyncRedis:
    def __init__(self, store: dict[str, str]) -> None:
        self.store = store

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None:
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True


class FakeTTLCacheAsyncRedis:
    def __init__(self, store: dict[str, str]) -> None:
        self.store = store

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None:
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True


def pytest_configure(config: pytest.Config) -> None:
    """Drop all tables in test_db before test session begins + drop redis cache."""
    url = os.getenv("TEST_URL")
    if url is None:
        return
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.commit()
    engine.dispose()

    with r.Redis(host="test_redis", port=6379) as red:
        red.flushall()
        red.close()


pytest_plugins = [
    "tests.fixtures.populators.sample",
    "tests.fixtures.populators.xianxia",
    "tests.fixtures.populators.scifi",
    "tests.fixtures.populators.permissions_one",
    "tests.fixtures.populators.label_permissions",
    "tests.fixtures.populators.novel_permissions",
    "tests.fixtures.password_hash",
    "tests.fixtures.populators.score_filter_simple",
    "tests.fixtures.populators.text_ops",
    "tests.fixtures.populators.bundles",
    "tests.fixtures.filters",
]


@pytest.fixture
def test_url() -> str:
    ret = os.getenv("TEST_URL")
    if ret is None:
        raise OSError("TEST_URL environment variable not set for tests.")
    return ret


@pytest.fixture
def ttl_cache_store() -> dict[str, str]:
    return {}


@pytest.fixture(autouse=True)
def fake_ttl_cache_redis(monkeypatch: pytest.MonkeyPatch, ttl_cache_store: dict[str, str]) -> dict[str, Any]:
    import src.requests.cache as cache_module

    sync_redis = FakeTTLCacheSyncRedis(ttl_cache_store)
    async_redis = FakeTTLCacheAsyncRedis(ttl_cache_store)

    monkeypatch.setattr(cache_module, "get_redis_for_ttl_cache_sync", lambda: sync_redis)
    monkeypatch.setattr(cache_module, "get_redis_for_ttl_cache_async", lambda: async_redis)

    return {"sync": sync_redis, "async": async_redis, "store": ttl_cache_store}


@pytest.fixture
def test_engine(test_url: str) -> Engine:
    engine = create_engine(test_url)
    return engine


@pytest.fixture
def testing_session_local(test_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def test_db(test_engine: Engine, testing_session_local: sessionmaker[Session]) -> Generator[Session, None, None]:
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
    pool = await create_pool(RedisSettings(host="test_redis", port=6379, database=0))
    yield pool
    await pool.aclose()


@pytest.fixture
async def worker_mock(test_url: str, monkeypatch: pytest.MonkeyPatch, redis: ArqRedis) -> Worker:
    import src.autolabels.worker.tasks as worker_cfg

    # infer_autolabels uses worker_cfg.SessionLocal to configure its database connection
    monkeypatch.setattr(worker_cfg, "SessionLocal", sessionmaker(create_engine(test_url)))

    return Worker(
        functions=WorkerSettings.functions,
        redis_pool=redis,
        on_startup=WorkerSettings.on_startup,
        burst=True,
        poll_delay=0,
    )


@pytest.fixture
def client(test_db: Session, redis: ArqRedis):
    def override_get_db():
        yield test_db

    def override_get_redis_for_app():
        return redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_for_app] = override_get_redis_for_app
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class DataLoader:
    """
    Class for a data loader. Callable class.
    """

    def __init__(self, base_path: Path, pattern: str):
        self.base_path = base_path
        self.pattern = pattern

    def _load(self, subdir: str = "", recursive: bool = False) -> Generator[str, None, None]:
        target_dir = self.base_path / subdir

        if not target_dir.exists():
            raise FileNotFoundError(f"Test data directory not found: {target_dir}\nCurrent base path: {self.base_path}")
        files = target_dir.rglob(self.pattern) if recursive else target_dir.glob(self.pattern)
        sorted_files = sorted(files, key=lambda p: p.name)
        for f in sorted_files:
            yield f.read_text(encoding="utf-8")

    def __call__(self, subdir: str = "", recursive: bool = False) -> Generator[str, None, None]:
        return self._load(subdir, recursive)


@pytest.fixture
def chapter_loader() -> DataLoader:
    """
    Returns a chapter loader callable that takes a pathname in the `test_data/chapters/` directory (e.g. if `chapters/chinese` contains `chapter_1.txt`, `chapter_2.txt`), then calling `chapter_loader().load("chinese")` should return a generator of strings containing the content in `chapter_1.txt` and `chapter_2.txt`.
    Calling with the recursive flag will return the contents of all subdirectories as well (e.g. `chapter_loader().load("", recursive=True)` will also return chapters in `chapters/korean`, if that is a folder).
    """
    base_path = Path(__file__).parent / "test_data" / "chapters"
    return DataLoader(base_path, "*.txt")


@pytest.fixture
def autolabel_loader() -> DataLoader:
    """
    Returns an autolabel loader callable that takes a pathname in the `test_data/autolabel/` directory (e.g. if `chapters/chinese` contains `chapter_1.json', `chapter_2.json`), then calling `autolabel_loader().load("chinese")` should return a generator of strings containing the content in `chapter_1.json` and `chapter_2.json`
    Calling with the recursive flag will return the contents of all subdirectories as well (e.g. `autolabel().load("", recursive=True)` will also return chapters in `autolabels/korean`, if that is a folder).
    """
    base_path = Path(__file__).parent / "test_data" / "autolabels"
    return DataLoader(base_path, "*.json")


@pytest.fixture(scope="session")
def cluener_testconfig_params():
    """
    Load cluener model params from tests/test_data/testconfig.json.

    Returns a ``CluenerParams`` instance, suitable for passing directly to
    model prediction or serialising in ``CreateLabelDataByAutoLabel``.

    Raises a ``RuntimeError`` if ``testconfig.json`` differs from
    ``testconfig.lock.json``, indicating that the autolabel test data was
    generated with a different config and must be regenerated.
    """
    from src.autolabels.constants import SepPriority
    from src.autolabels.params import CluenerParams

    config_path = Path(__file__).parent / "test_data" / "testconfig.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    lock_path = config_path.parent / "testconfig.lock.json"
    if lock_path.exists():
        lock_config = json.loads(lock_path.read_text(encoding="utf-8"))
        if json.dumps(config, sort_keys=True) != json.dumps(lock_config, sort_keys=True):
            raise RuntimeError(
                "testconfig.json differs from testconfig.lock.json.\n"
                "Regenerate autolabel test data with:\n"
                "  uv run -m scripts.populate_test_data"
            )

    model_config = config["models"]["cluener"]

    sep_map = {"high": SepPriority.HIGH, "med": SepPriority.MED, "low": SepPriority.LOW}
    return CluenerParams(
        model_name="cluener",
        chunk_size=model_config["chunk_size"],
        separators={k: sep_map[str(v).lower()] for k, v in model_config["separators"].items()},
        force_chunk=model_config.get("force_chunk", False),
    )
