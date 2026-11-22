"""
This module provides modules for database connection.
"""

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import database_settings

engine: Engine = create_engine(database_settings.DB_URL)
SessionLocal: sessionmaker[Session] = sessionmaker(autoflush=False, bind=engine)

# Async sessions cannot lazily refresh attributes expired by a commit, so commits keep loaded values.
async_engine: AsyncEngine = create_async_engine(database_settings.DB_URL)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine, autoflush=False, expire_on_commit=False
)


def get_db() -> Generator[Session]:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as db:
        yield db
