import re
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from src.models import Base

_DATABASE_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class TemporaryPostgresDatabase:
    name: str
    engine: Engine
    session_factory: Any


@contextmanager
def temporary_postgres_database(
    server_url: str,
    *,
    prefix: str = "agent_eval",
) -> Generator[TemporaryPostgresDatabase, None, None]:
    """Create a UUID-named PostgreSQL database and remove it on exit."""

    if not _DATABASE_PREFIX_PATTERN.fullmatch(prefix) or len(prefix) > 30:
        raise ValueError("prefix must be at most 30 lowercase letters, digits, and underscores")

    database_name = f"{prefix}_{uuid.uuid4().hex}"
    server = make_url(server_url)
    if server.get_backend_name() != "postgresql":
        raise ValueError("evaluation database URL must use PostgreSQL")
    maintenance_url = server.set(database="postgres")
    database_url = server.set(database=database_name)
    maintenance_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    database_engine: Engine | None = None
    created = False

    try:
        with maintenance_engine.connect() as connection:
            quoted_name = connection.dialect.identifier_preparer.quote(database_name)
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
            created = True

        database_engine = create_engine(database_url, poolclass=NullPool)
        with database_engine.begin() as connection:
            connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS btree_gist")
        metadata_bind: Any = database_engine
        Base.metadata.create_all(bind=metadata_bind)

        yield TemporaryPostgresDatabase(
            name=database_name,
            engine=database_engine,
            session_factory=sessionmaker(autoflush=False, bind=database_engine),
        )
    finally:
        if database_engine is not None:
            database_engine.dispose()
        if created:
            with maintenance_engine.connect() as connection:
                quoted_name = connection.dialect.identifier_preparer.quote(database_name)
                connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {quoted_name} WITH (FORCE)")
        maintenance_engine.dispose()
