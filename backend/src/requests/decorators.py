import uuid
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, cast

from fastapi import HTTPException
from pydantic import BaseModel

from .cache import TTLCache


def ttl_cache[**P, R : BaseModel](cache: TTLCache, ttl: int, success_code : int = 200, serialize_ret : Callable[[R], dict] | None = None) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to optionally cache the result of a function. Must have a request_key: uuid.UUID | None as a kwarg.

    Args:
        cache: The TTLCache to use for caching results.
        ttl: The time-to-live for cache entries in seconds.
        success_code: The HTTP status code to set in the cache entry on success.
        serialize_ret: A function to serialize the return value before caching.

    Returns:
        A decorated version of func that caches results in cache.
    """
    def inner_decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args,  **kwargs: P.kwargs, ) -> R:
            request_key = cast(uuid.UUID | None, kwargs["request_key"])
            if (request_key is None):
                return func(*args, **kwargs)
            if not cache.insert(request_key, {"status": "pending", "status_code": None, "response": None, "error": None}, expire=ttl):
                raise HTTPException(
                    status_code=409,
                    detail={"detail": "Request with same request_key already exists.", "cacheConflict": True},
                )
            try:
                result = func(*args, **kwargs)
                cache.set(request_key, {"status": "success", "status_code": success_code, "response": serialize_ret(result) if serialize_ret else None, "error": None}, expire=ttl)
                return result
            except HTTPException as e:
                cache.set(request_key, {"status": "failure", "status_code": e.status_code, "response": None, "error": {"detail": e.detail, "cacheConflict": False}}, expire=ttl)
                if e.status_code == 409:
                    raise HTTPException(
                        status_code=409,
                        detail={"detail": e.detail, "cacheConflict": False},
                    ) from e
                raise
            except Exception as e:
                cache.set(request_key, {"status": "failure", "status_code": 500, "response": None, "error": { "detail": str(e), "cacheConflict": False }}, expire=ttl)
                raise
        return wrapper
    return inner_decorator

def attl_cache[**P, R : BaseModel](cache: TTLCache, ttl: int, success_code : int = 200, serialize_ret : Callable[[R], dict] | None = None) -> Callable[[Callable[P, Coroutine[None, None, R]]], Callable[P, Coroutine[None, None, R]]]:
    """
    Decorator to optionally cache the result of a async function. Must have a request_key: uuid.UUID | None as a kwarg.

    Args:
        func: The function to be decorated.
        cache: The TTLCache to use for caching results.
        ttl: The time-to-live for cache entries in seconds.
        success_code: The HTTP status code for successful responses.

    Returns:
        A decorated version of func that caches results in cache.
    """
    def inner_decorator(func: Callable[P, Coroutine[None, None, R]]) -> Callable[P, Coroutine[None, None, R]]:
        @wraps(func)
        async def wrapper(*args: P.args,  **kwargs: P.kwargs) -> R:
            request_key = cast(uuid.UUID | None, kwargs["request_key"])
            if (request_key is None):
                return await func(*args, **kwargs)
            if not await cache.ainsert(request_key, {"status": "pending", "status_code": None, "response": None, "error": None}, expire=ttl):
                raise HTTPException(
                    status_code=409,
                    detail={"detail": "Request with same request_key already exists.", "cacheConflict": True},
                )
            try:
                result = await func(*args, **kwargs)
                await cache.aset(request_key, {"status": "success", "status_code": success_code, "response": serialize_ret(result) if serialize_ret else None, "error": None}, expire=ttl)
                return result
            except HTTPException as e:
                await cache.aset(request_key, {"status": "failure", "status_code": e.status_code, "response": None, "error": { "detail": e.detail, "cacheConflict": False }}, expire=ttl)
                if e.status_code == 409:
                    raise HTTPException(
                        status_code=409,
                        detail={"detail": e.detail, "cacheConflict": False},
                    ) from e
                raise
            except Exception as e:
                await cache.aset(request_key, {"status": "failure", "status_code": 500, "response": None, "error": { "detail": str(e), "cacheConflict": False }}, expire=ttl)
                raise
        return wrapper
    return inner_decorator

def svp(result_t: type[BaseModel]) -> Callable[[Any], dict]:
    """
    I forgot what this stands for. Returns a function that takes in an instance of result_t or something that can be parsed into result_t and returns a dict that can be returned as a JSON response.
    """
    def serializer(to_serialize : Any) -> dict:
        return result_t.model_validate(to_serialize).model_dump(mode="json")
    return serializer
