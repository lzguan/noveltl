import re
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from src.models import Base

_DATABASE_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class TemporaryPostgresDatabase:
    name: str
    engine: Engine
    session_factory: sessionmaker[Session]


@contextmanager
def temporary_postgres_database(
    server_url: str,
    *,
    prefix: str = "noveltl_test",
) -> Generator[TemporaryPostgresDatabase, None, None]:
    """Create an isolated PostgreSQL database and remove it on exit."""
    if not _DATABASE_PREFIX_PATTERN.fullmatch(prefix) or len(prefix) > 30:
        raise ValueError("prefix must be at most 30 lowercase letters, digits, and underscores")

    database_name = f"{prefix}_{uuid.uuid4().hex}"
    database_url = make_url(server_url)
    if database_url.get_backend_name() != "postgresql":
        raise ValueError("server_url must use PostgreSQL")
    maintenance_url = database_url.set(database="postgres")
    database_url = database_url.set(database=database_name)
    maintenance_engine = create_engine(
        maintenance_url,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    database_engine: Engine | None = None
    database_created = False

    try:
        with maintenance_engine.connect() as connection:
            quoted_name = connection.dialect.identifier_preparer.quote(database_name)
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
            database_created = True

        database_engine = create_engine(database_url, poolclass=NullPool)
        with database_engine.begin() as connection:
            connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS btree_gist")
            Base.metadata.create_all(bind=connection)

        yield TemporaryPostgresDatabase(
            name=database_name,
            engine=database_engine,
            session_factory=sessionmaker(autoflush=False, bind=database_engine),
        )
    finally:
        if database_engine is not None:
            database_engine.dispose()
        if database_created:
            with maintenance_engine.connect() as connection:
                quoted_name = connection.dialect.identifier_preparer.quote(database_name)
                connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {quoted_name} WITH (FORCE)")
        maintenance_engine.dispose()
