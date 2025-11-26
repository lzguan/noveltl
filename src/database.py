"""
This module provides modules for database connection.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import database_settings

engine = create_engine(database_settings.DB_URL)
SessionLocal = sessionmaker(autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()