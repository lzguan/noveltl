from arq import ArqRedis, create_pool
from .config import redis_settings, uvicorn_logger
from contextlib import asynccontextmanager
from .exceptions import RedisNotInitializedError
from fastapi import HTTPException, status

redis : ArqRedis | None = None

@asynccontextmanager
async def set_redis():
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
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Request queueing down."
    )