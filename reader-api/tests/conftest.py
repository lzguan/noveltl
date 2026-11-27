import os
from collections.abc import AsyncGenerator, Callable, Generator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from src.auth import generate_api_key
from src.database import get_async_db
from src.main import app
from src.models import Base, ReaderPartner, ReaderPartnerKey

READER_API_ROOT = Path(__file__).resolve().parent.parent
FALLBACK_TEST_DB_NAME = "reader_test"


def _resolve_reader_test_url() -> str:
    explicit = os.getenv("READER_TEST_DB_URL", "").strip()
    if explicit:
        return explicit

    studio_test_url = os.getenv("TEST_URL", "").strip()
    if not studio_test_url:
        raise OSError("Neither READER_TEST_DB_URL nor TEST_URL is set for reader-api tests.")

    parsed = make_url(studio_test_url)
    admin_engine = create_engine(studio_test_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": FALLBACK_TEST_DB_NAME},
            ).scalar_one_or_none()
            if exists is None:
                conn.execute(text(f'CREATE DATABASE "{FALLBACK_TEST_DB_NAME}"'))
    finally:
        admin_engine.dispose()

    return parsed.set(database=FALLBACK_TEST_DB_NAME).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def reader_test_url() -> str:
    return _resolve_reader_test_url()


@pytest.fixture(scope="session")
def database_schema(reader_test_url: str) -> Generator[None]:
    engine = create_engine(reader_test_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            conn.commit()

        alembic_cfg = Config(str(READER_API_ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(READER_API_ROOT / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", reader_test_url)
        command.upgrade(alembic_cfg, "head")
        command.check(alembic_cfg)
        yield
    finally:
        engine.dispose()


@pytest.fixture
def sync_engine(reader_test_url: str) -> Generator[Engine]:
    engine = create_engine(reader_test_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def async_engine_fixture(reader_test_url: str) -> Generator[AsyncEngine]:
    engine = create_async_engine(reader_test_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.sync_engine.dispose()


@pytest.fixture
def async_session_factory(
    database_schema: None,
    sync_engine: Engine,
    async_engine_fixture: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    with sync_engine.begin() as conn:
        tables = ", ".join(
            conn.dialect.identifier_preparer.format_table(table) for table in Base.metadata.sorted_tables
        )
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    return async_sessionmaker(async_engine_fixture, autoflush=False, expire_on_commit=False)


@pytest.fixture
async def db_session(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


@pytest.fixture
def client(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[TestClient]:
    async def override_get_async_db() -> AsyncGenerator[AsyncSession]:
        async with async_session_factory() as db:
            yield db

    app.dependency_overrides[get_async_db] = override_get_async_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def create_partner_with_key(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[str], tuple[ReaderPartner, ReaderPartnerKey, str]]:
    import asyncio

    def _create(name: str) -> tuple[ReaderPartner, ReaderPartnerKey, str]:
        async def _inner() -> tuple[ReaderPartner, ReaderPartnerKey, str]:
            async with async_session_factory() as db:
                partner = ReaderPartner(name=name)
                db.add(partner)
                await db.flush()
                raw_key, prefix, key_hash = generate_api_key()
                key = ReaderPartnerKey(
                    partner_id=partner.partner_id,
                    key_prefix=prefix,
                    key_hash=key_hash,
                )
                db.add(key)
                await db.commit()
                await db.refresh(partner)
                await db.refresh(key)
                return partner, key, raw_key

        return asyncio.run(_inner())

    return _create
