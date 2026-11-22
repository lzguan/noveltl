from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.languages.models import Language


async def test_async_session_sees_rows_committed_by_the_sync_session(test_db: Session, async_test_db: AsyncSession):
    test_db.add(Language(language_code="xx", language_name="Test language"))
    test_db.commit()

    names = (await async_test_db.scalars(select(Language.language_name).where(Language.language_code == "xx"))).all()

    assert names == ["Test language"]


async def test_async_session_keeps_attributes_loaded_after_commit(async_test_db: AsyncSession):
    language = Language(language_code="xy", language_name="Kept after commit")
    async_test_db.add(language)
    await async_test_db.commit()

    # Reading an expired attribute would need an implicit refresh query, which an async session cannot run.
    assert language.language_name == "Kept after commit"
