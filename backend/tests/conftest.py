import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.autolabels.dependencies import get_dispatcher
from src.database import get_db
from src.filters.dependencies import get_dispatcher as get_filter_dispatcher
from src.main import app
from src.models import Base
from test_support.autolabels import RecordingDispatcher
from test_support.filters import RecordingRunnerDispatcher
from test_support.test_data import Catalog, NovelDataset, load_catalog, load_config, load_novel

SYNTHETIC_DATA_ROOT = Path(__file__).parent / "test_data" / "datasets" / "synthetic-smoke"
LEGACY_DATA_ROOT = Path(__file__).parent / "test_data" / "datasets" / "legacy-corpora"


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
    """Drop all tables in test_db before the test session begins."""
    url = os.getenv("TEST_URL")
    if url is None:
        return
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.commit()
    engine.dispose()


pytest_plugins = [
    "tests.fixtures.scenarios",
    "tests.fixtures.password_hash",
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
def recording_dispatcher() -> RecordingDispatcher:
    return RecordingDispatcher()


@pytest.fixture
def recording_runner_dispatcher() -> RecordingRunnerDispatcher:
    return RecordingRunnerDispatcher()


@pytest.fixture
def client(
    test_db: Session,
    recording_dispatcher: RecordingDispatcher,
    recording_runner_dispatcher: RecordingRunnerDispatcher,
):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_dispatcher] = lambda: recording_dispatcher
    app.dependency_overrides[get_filter_dispatcher] = lambda: recording_runner_dispatcher
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def synthetic_test_catalog() -> Catalog:
    return load_catalog(SYNTHETIC_DATA_ROOT)


@pytest.fixture(scope="session")
def xianxia_test_dataset(synthetic_test_catalog: Catalog) -> NovelDataset:
    return load_novel(synthetic_test_catalog, "xianxia-source")


@pytest.fixture(scope="session")
def scifi_test_dataset(synthetic_test_catalog: Catalog) -> NovelDataset:
    return load_novel(synthetic_test_catalog, "xianxia-translation")


@pytest.fixture(scope="session")
def legacy_test_catalog() -> Catalog:
    return load_catalog(LEGACY_DATA_ROOT)


@pytest.fixture(scope="session")
def qingyun_test_dataset(legacy_test_catalog: Catalog) -> NovelDataset:
    return load_novel(legacy_test_catalog, "qingyun")


@pytest.fixture(scope="session")
def quantum_path_test_dataset(legacy_test_catalog: Catalog) -> NovelDataset:
    return load_novel(legacy_test_catalog, "quantum-path")


@pytest.fixture(scope="session")
def starfall_test_dataset(legacy_test_catalog: Catalog) -> NovelDataset:
    return load_novel(legacy_test_catalog, "starfall")


@pytest.fixture(scope="session")
def silverleaf_test_dataset(legacy_test_catalog: Catalog) -> NovelDataset:
    return load_novel(legacy_test_catalog, "silverleaf")


@pytest.fixture(scope="session")
def cluener_testconfig_params(synthetic_test_catalog: Catalog):
    """
    Load CLUENER parameters from the committed synthetic dataset.

    Returns a ``CluenerParams`` instance, suitable for passing directly to
    model prediction or serialising in ``CreateLabelDataByAutoLabel``.

    Dataset consistency is verified through ``catalog.lock.json``.
    """
    from src.autolabels.constants import SepPriority
    from src.autolabels.params import CluenerParams

    config = load_config(synthetic_test_catalog, "cluener-default")
    sep_map = {"high": SepPriority.HIGH, "med": SepPriority.MED, "low": SepPriority.LOW}
    return CluenerParams(
        model_name=config.model_name,
        chunk_size=config.parameters.chunk_size,
        separators={key: sep_map[value] for key, value in config.parameters.separators.items()},
        force_chunk=config.parameters.force_chunk,
    )
