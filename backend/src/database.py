"""
This module provides modules for database connection.
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import database_settings

engine: Engine = create_engine(database_settings.DB_URL)
SessionLocal: sessionmaker[Session] = sessionmaker(autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
