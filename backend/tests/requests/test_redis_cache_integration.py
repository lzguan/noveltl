import asyncio
import os
import time
import uuid

import pytest
import redis

import src.requests.cache as cache_module
from src.requests.cache import CacheEntry, RedisCache

pytestmark = pytest.mark.integration

REDIS_TEST_DATABASE = 13


@pytest.mark.asyncio
async def test_redis_cache_preserves_entries_conflicts_and_expiration(monkeypatch: pytest.MonkeyPatch) -> None:
    host = os.getenv("TEST_REDIS_HOST", "test_redis")
    port = int(os.getenv("TEST_REDIS_PORT", "6379"))
    sync_client = redis.Redis(host=host, port=port, db=REDIS_TEST_DATABASE, decode_responses=True)
    async_client = redis.asyncio.Redis(host=host, port=port, db=REDIS_TEST_DATABASE, decode_responses=True)
    sync_client.flushdb()
    monkeypatch.setattr(cache_module, "get_redis_for_ttl_cache_sync", lambda: sync_client)
    monkeypatch.setattr(cache_module, "get_redis_for_ttl_cache_async", lambda: async_client)
    cache = RedisCache()

    initial: CacheEntry = {
        "status": "pending",
        "status_code": None,
        "response": None,
        "error": None,
    }
    success: CacheEntry = {
        "status": "success",
        "status_code": 200,
        "response": {"chapterContentId": str(uuid.uuid4()), "version": 2},
        "error": None,
    }

    try:
        sync_key = uuid.uuid4()
        assert cache.insert(sync_key, initial, expire=30) is True
        assert cache.insert(sync_key, success, expire=30) is False
        assert cache.get(sync_key) == initial

        cache.set(sync_key, success, expire=1)
        assert cache.get(sync_key) == success
        assert sync_client.ttl(str(sync_key)) in {0, 1}

        deadline = time.monotonic() + 2
        while cache.get(sync_key) is not None and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        assert cache.get(sync_key) is None

        async_key = uuid.uuid4()
        assert await cache.ainsert(async_key, initial, expire=30) is True
        assert await cache.ainsert(async_key, success, expire=30) is False
        assert await cache.aget(async_key) == initial

        await cache.aset(async_key, success, expire=30)
        assert cache.get(async_key) == success
    finally:
        sync_client.flushdb()
        sync_client.close()
        await async_client.aclose()
