import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, TextClause, create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from src.autolabels.dependencies import get_dispatcher, get_promotion_dispatcher
from src.database import get_async_db, get_db
from src.datasets import Catalog, NovelDataset, load_catalog, load_config, load_novel
from src.filters.dependencies import get_dispatcher as get_filter_dispatcher
from src.main import app
from src.memory.agent.dispatch.dependencies import get_dispatcher as get_memory_agent_dispatcher
from src.models import Base
from test_support.autolabels import RecordingDispatcher, RecordingPromotionDispatcher
from test_support.filters import RecordingRunnerDispatcher
from test_support.memory import RecordingMemoryAgentDispatcher

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


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="session")
def test_engine(test_url: str) -> Generator[Engine]:
    engine = create_engine(test_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def testing_session_local(test_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# NullPool: TestClient runs the app on its own event loop, and pooled async
# connections cannot move between loops.
@pytest.fixture(scope="session")
def test_async_engine(test_url: str) -> Generator[AsyncEngine]:
    engine = create_async_engine(test_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.sync_engine.dispose()


@pytest.fixture(scope="session")
def testing_async_session_local(test_async_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_async_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session")
def database_schema(test_engine: Engine) -> Generator[None]:
    with test_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture(scope="session")
def _table_reset_plan(database_schema: None, test_engine: Engine) -> tuple[list[str], TextClause]:
    preparer = test_engine.dialect.identifier_preparer
    formatted_tables = [preparer.format_table(t) for t in Base.metadata.sorted_tables]
    non_empty_query = text(
        " UNION ALL ".join(f"(SELECT {i} AS idx FROM {t} LIMIT 1)" for i, t in enumerate(formatted_tables))
    )
    return formatted_tables, non_empty_query


@pytest.fixture(scope="function")
def test_db(
    _table_reset_plan: tuple[list[str], TextClause],
    test_engine: Engine,
    testing_session_local: sessionmaker[Session],
) -> Generator[Session]:
    """Creates a new database session for a test."""
    formatted_tables, non_empty_query = _table_reset_plan
    with test_engine.begin() as connection:
        dirty_indexes = [i for i in connection.scalars(non_empty_query) if isinstance(i, int)]
        if dirty_indexes:
            delete_sql = "; ".join(f"DELETE FROM {formatted_tables[i]}" for i in reversed(dirty_indexes))
            connection.execute(text(delete_sql))

    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
async def async_test_db(
    test_db: Session, testing_async_session_local: async_sessionmaker[AsyncSession]
) -> AsyncGenerator[AsyncSession]:
    async with testing_async_session_local() as db:
        yield db


@pytest.fixture
def recording_dispatcher() -> RecordingDispatcher:
    return RecordingDispatcher()


@pytest.fixture
def recording_promotion_dispatcher() -> RecordingPromotionDispatcher:
    return RecordingPromotionDispatcher()


@pytest.fixture
def recording_runner_dispatcher() -> RecordingRunnerDispatcher:
    return RecordingRunnerDispatcher()


@pytest.fixture
def recording_memory_agent_dispatcher() -> RecordingMemoryAgentDispatcher:
    return RecordingMemoryAgentDispatcher()


@pytest.fixture
def client(
    test_db: Session,
    testing_async_session_local: async_sessionmaker[AsyncSession],
    recording_dispatcher: RecordingDispatcher,
    recording_promotion_dispatcher: RecordingPromotionDispatcher,
    recording_runner_dispatcher: RecordingRunnerDispatcher,
    recording_memory_agent_dispatcher: RecordingMemoryAgentDispatcher,
):
    def override_get_db():
        yield test_db

    async def override_get_async_db():
        async with testing_async_session_local() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_db] = override_get_async_db
    app.dependency_overrides[get_dispatcher] = lambda: recording_dispatcher
    app.dependency_overrides[get_promotion_dispatcher] = lambda: recording_promotion_dispatcher
    app.dependency_overrides[get_filter_dispatcher] = lambda: recording_runner_dispatcher
    app.dependency_overrides[get_memory_agent_dispatcher] = lambda: recording_memory_agent_dispatcher
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
