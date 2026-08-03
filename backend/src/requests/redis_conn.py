import redis

from src.config import redis_settings

redis_for_ttl_cache_sync = redis.Redis(
    host=redis_settings.REDIS_HOST, port=redis_settings.REDIS_PORT, db=redis_settings.REQUESTS_DATABASE
)

redis_for_ttl_cache_async = redis.asyncio.Redis(
    host=redis_settings.REDIS_HOST, port=redis_settings.REDIS_PORT, db=redis_settings.REQUESTS_DATABASE
)


def get_redis_for_ttl_cache_sync() -> redis.Redis:
    return redis_for_ttl_cache_sync


def get_redis_for_ttl_cache_async() -> redis.asyncio.Redis:
    return redis_for_ttl_cache_async
