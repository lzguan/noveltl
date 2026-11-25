from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.config import reader_settings

async_engine: AsyncEngine = create_async_engine(reader_settings.READER_DB_URL)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine, autoflush=False, expire_on_commit=False
)


async def get_async_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as db:
        yield db
