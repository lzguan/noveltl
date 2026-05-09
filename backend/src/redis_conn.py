from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis
from arq import ArqRedis, create_pool
from fastapi import HTTPException, status

from .config import _redis_settings, redis_settings
from .exceptions import RedisNotInitializedError

redis_for_worker: ArqRedis | None = None

redis_for_ttl_cache_sync = redis.Redis(host=_redis_settings.REDIS_HOST, port=_redis_settings.REDIS_PORT, db=1)

redis_for_ttl_cache_async = redis.asyncio.Redis(host=_redis_settings.REDIS_HOST, port=_redis_settings.REDIS_PORT, db=1)


@asynccontextmanager
async def set_redis() -> AsyncGenerator[None]:
    global redis_for_worker
    redis_for_worker = await create_pool(redis_settings)
    yield
    await redis_for_worker.aclose()


def get_redis() -> ArqRedis:
    if redis_for_worker is not None:
        return redis_for_worker
    raise RedisNotInitializedError


def get_redis_for_app() -> ArqRedis:
    if redis_for_worker is not None:
        return redis_for_worker
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Request queueing down.")


def get_redis_for_ttl_cache_sync() -> redis.Redis:
    return redis_for_ttl_cache_sync


def get_redis_for_ttl_cache_async() -> redis.asyncio.Redis:
    return redis_for_ttl_cache_async
