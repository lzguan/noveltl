import pytest
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, List, Dict

from src.models import Base
from src.languages.models import Language
from src.novels.models import Novel


TEST_URL = os.getenv("TEST_URL")
if TEST_URL is None:
    raise EnvironmentError("TEST_URL environment variable not set for tests.")

engine = create_engine(TEST_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Creates a new database session for a test."""
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        connection.commit()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_languages(db_session : Session) -> Dict[str, Language]:
    # Create the standard languages needed for most tests
    en = Language(language_name="English", language_code="en")
    zh = Language(language_name="Chinese", language_code="zh")
    kr = Language(language_name="Korean", language_code="kr")
    jp = Language(language_name="Japanese", language_code="jp")
    db_session.add_all([en, zh, kr, jp])
    db_session.commit()
    db_session.refresh(en)
    db_session.refresh(zh)
    db_session.refresh(kr)
    db_session.refresh(jp)
    return {"en": en, "zh": zh, "kr": kr, "jp": jp}

@pytest.fixture
def sample_novels(sample_languages : dict[str, Language], db_session : Session) -> List[Novel]:
    # Create some sample novels
    novel0 = Novel(novel_title="Sample Novel 1", language_id=sample_languages['en'].language_id)
    novel1 = Novel(novel_title="Sample Novel 2", language_id=sample_languages['zh'].language_id)
    novel2 = Novel(novel_title="Sample Novel 3", language_id=sample_languages['kr'].language_id, novel_description="A description.", novel_author="An Author")
    novel3 = Novel(novel_title="Smample Novel 4", language_id=sample_languages['zh'].language_id, novel_description="Another description.", novel_author="Another Author")
    db_session.add_all([novel0, novel1, novel2, novel3])
    db_session.commit()
    db_session.refresh(novel0)

    db_session.refresh(novel1)
    db_session.refresh(novel2)
    db_session.refresh(novel3)
    return [novel0, novel1, novel2, novel3]