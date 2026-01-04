from arq import ArqRedis, create_pool
from .config import redis_settings, uvicorn_logger
from contextlib import asynccontextmanager

redis : ArqRedis | None = None

@asynccontextmanager
async def set_redis():
    global redis
    redis = await create_pool(redis_settings)
    uvicorn_logger.info(redis)
    yield
    await redis.close()
    uvicorn_logger.info("redis closed")

def get_redis() -> ArqRedis | None:
    return redis