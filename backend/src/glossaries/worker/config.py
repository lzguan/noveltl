from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ... import config

DB_URL = config.database_settings.DB_URL
REDIS_HOST = "redis"
REDIS_PORT = 6379

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autoflush=False, bind=engine)
