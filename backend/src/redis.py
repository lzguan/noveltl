from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from arq import ArqRedis, create_pool
from fastapi import HTTPException, status

from .config import redis_settings
from .exceptions import RedisNotInitializedError

redis: ArqRedis | None = None


@asynccontextmanager
async def set_redis() -> AsyncGenerator[None]:
    global redis
    redis = await create_pool(redis_settings)
    yield
    await redis.aclose()


def get_redis() -> ArqRedis:
    if redis is not None:
        return redis
    raise RedisNotInitializedError


def get_redis_for_app() -> ArqRedis:
    if redis is not None:
        return redis
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Request queueing down."
    )
