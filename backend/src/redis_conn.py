import redis

from src.config import redis_settings

redis_for_ttl_cache_sync = redis.Redis(host=redis_settings.REDIS_HOST, port=redis_settings.REDIS_PORT, db=1)

redis_for_ttl_cache_async = redis.asyncio.Redis(host=redis_settings.REDIS_HOST, port=redis_settings.REDIS_PORT, db=1)


def get_redis_for_ttl_cache_sync() -> redis.Redis:
    return redis_for_ttl_cache_sync


def get_redis_for_ttl_cache_async() -> redis.asyncio.Redis:
    return redis_for_ttl_cache_async
