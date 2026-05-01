import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from src.schemas import ErrorResponse
from src.requests.cache import TTLCache
from src.requests.dependencies import get_redis_cache

from .cache import CacheEntry

router = APIRouter()

@router.get(
    '/cached/{cachedId}',
    responses={
        404: {"model": ErrorResponse, "description": "Cached result not found."},
    },
)
def get_cached_result(cached_id: Annotated[uuid.UUID, Path(alias="cachedId")], cache : Annotated[TTLCache, Depends(get_redis_cache)]) -> CacheEntry:
    cached_result = cache.get(cached_id)
    if cached_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cached result not found.")
    return cached_result
