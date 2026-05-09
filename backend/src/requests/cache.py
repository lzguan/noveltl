"""
Cache decorators for request results. Record results/status of requests in a TTL cache to allow clients to poll for results of long-running requests without needing to re-run the request.
"""

import json
import uuid
from typing import Literal, Protocol, TypedDict

from ..redis_conn import get_redis_for_ttl_cache_async, get_redis_for_ttl_cache_sync

RequestStatus = Literal["pending", "success", "failure"]


class CacheError(TypedDict):
    detail: str
    cacheConflict: bool


class CacheEntry(TypedDict):
    status: RequestStatus
    status_code: int | None
    response: dict | None
    error: CacheError | None


class TTLCache(Protocol):
    def get(self, key: uuid.UUID) -> CacheEntry | None: ...
    def set(self, key: uuid.UUID, value: CacheEntry, expire: int) -> None: ...
    def insert(self, key: uuid.UUID, value: CacheEntry, expire: int) -> bool: ...
    async def aget(self, key: uuid.UUID) -> CacheEntry | None: ...
    async def aset(self, key: uuid.UUID, value: CacheEntry, expire: int) -> None: ...
    async def ainsert(self, key: uuid.UUID, value: CacheEntry, expire: int) -> bool: ...


class RedisCache(TTLCache):
    def __init__(self):
        pass

    def get(self, key: uuid.UUID) -> CacheEntry | None:
        value = get_redis_for_ttl_cache_sync().get(str(key))
        if value is not None:
            return json.loads(value)  # type: ignore
        return None

    def set(self, key: uuid.UUID, value: CacheEntry, expire: int) -> None:
        get_redis_for_ttl_cache_sync().set(str(key), json.dumps(value), ex=expire)

    def insert(self, key: uuid.UUID, value: CacheEntry, expire: int) -> bool:
        return True if get_redis_for_ttl_cache_sync().set(str(key), json.dumps(value), ex=expire, nx=True) else False

    async def aget(self, key: uuid.UUID) -> CacheEntry | None:
        value = await get_redis_for_ttl_cache_async().get(str(key))
        if value is not None:
            return json.loads(value)  # type: ignore
        return None

    async def aset(self, key: uuid.UUID, value: CacheEntry, expire: int) -> None:
        await get_redis_for_ttl_cache_async().set(str(key), json.dumps(value), ex=expire)

    async def ainsert(self, key: uuid.UUID, value: CacheEntry, expire: int) -> bool:
        return (
            True
            if await get_redis_for_ttl_cache_async().set(str(key), json.dumps(value), ex=expire, nx=True)
            else False
        )


redis_cache = RedisCache()
