import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.auth.models import User
from src.auth.utils import create_access_token
from src.novels.models import Novel
from src.requests.cache import CacheEntry, redis_cache
from src.requests.decorators import attl_cache, ttl_cache


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.user_name}, timedelta(minutes=30))}"}


class SampleResponse(BaseModel):
    value: int


class SpyCache:
    def __init__(self) -> None:
        self.store: dict[uuid.UUID, CacheEntry] = {}

    def get(self, key: uuid.UUID) -> CacheEntry | None:
        return self.store.get(key)

    def set(self, key: uuid.UUID, value: CacheEntry, expire: int) -> None:
        self.store[key] = value

    def insert(self, key: uuid.UUID, value: CacheEntry, expire: int) -> bool:
        if key in self.store:
            return False
        self.store[key] = value
        return True

    async def aget(self, key: uuid.UUID) -> CacheEntry | None:
        return self.store.get(key)

    async def aset(self, key: uuid.UUID, value: CacheEntry, expire: int) -> None:
        self.store[key] = value

    async def ainsert(self, key: uuid.UUID, value: CacheEntry, expire: int) -> bool:
        if key in self.store:
            return False
        self.store[key] = value
        return True


class TestRequestsRouter:
    def test_get_cached_result_returns_404_when_missing(self, client: TestClient) -> None:
        response = client.get(f"/cached/{uuid.uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Cached result not found."

    def test_get_cached_result_returns_cached_entry(self, client: TestClient) -> None:
        cached_id = uuid.uuid4()
        expected: CacheEntry = {
            "status": "success",
            "status_code": 200,
            "response": {"value": 3},
            "error": None,
        }
        redis_cache.set(cached_id, expected, expire=60)

        response = client.get(f"/cached/{cached_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

    def test_create_label_group_route_records_result(
        self,
        client: TestClient,
        sample_users: list[User],
        sample_novels: list[Novel],
        sample_contributors: object,
    ) -> None:
        request_key = uuid.uuid4()

        response = client.post(
            "/label-groups",
            params={"requestKey": str(request_key)},
            json={
                "novelId": str(sample_novels[1].novel_id),
                "labelGroupName": "Request Cache Group",
            },
            headers=_auth_headers(sample_users[1]),
        )

        assert response.status_code == status.HTTP_200_OK

        cached_response = client.get(f"/cached/{request_key}")
        assert cached_response.status_code == status.HTTP_200_OK
        assert cached_response.json()["status"] == "success"
        assert cached_response.json()["status_code"] == status.HTTP_200_OK
        assert cached_response.json()["response"]["label_group_name"] == "Request Cache Group"
        assert cached_response.json()["error"] is None

    def test_create_label_group_route_records_failure(
        self,
        client: TestClient,
        sample_users: list[User],
    ) -> None:
        request_key = uuid.uuid4()

        response = client.post(
            "/label-groups",
            params={"requestKey": str(request_key)},
            json={
                "novelId": str(uuid.uuid4()),
                "labelGroupName": "Request Cache Group",
            },
            headers=_auth_headers(sample_users[1]),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        cached_response = client.get(f"/cached/{request_key}")
        assert cached_response.status_code == status.HTTP_200_OK
        assert cached_response.json()["status"] == "failure"
        assert cached_response.json()["status_code"] == status.HTTP_404_NOT_FOUND
        assert cached_response.json()["response"] is None
        assert cached_response.json()["error"] == {
            "detail": "Novel associated with this label group not found.",
            "cacheConflict": False,
        }


class TestRequestDecorators:
    def test_ttl_cache_records_success(self) -> None:
        cache = SpyCache()
        request_key = uuid.uuid4()

        @ttl_cache(cache=cache, ttl=60, success_code=200, serialize_ret=lambda result: result.model_dump())
        def create_value(value: int, request_key: uuid.UUID | None = None) -> SampleResponse:
            return SampleResponse(value=value)

        result = create_value(7, request_key=request_key)

        assert result == SampleResponse(value=7)
        assert cache.store[request_key] == {
            "status": "success",
            "status_code": 200,
            "response": {"value": 7},
            "error": None,
        }

    def test_ttl_cache_records_http_failure(self) -> None:
        cache = SpyCache()
        request_key = uuid.uuid4()

        @ttl_cache(cache=cache, ttl=60, success_code=200, serialize_ret=lambda result: result.model_dump())
        def fail(request_key: uuid.UUID | None = None) -> SampleResponse:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="boom",
            )

        with pytest.raises(HTTPException):
            fail(request_key=request_key)

        assert cache.store[request_key] == {
            "status": "failure",
            "status_code": status.HTTP_409_CONFLICT,
            "response": None,
            "error": {"detail": "boom", "cacheConflict": False},
        }

    @pytest.mark.asyncio
    async def test_attl_cache_records_success(self) -> None:
        cache = SpyCache()
        request_key = uuid.uuid4()

        @attl_cache(cache=cache, ttl=60, success_code=200, serialize_ret=lambda result: result.model_dump())
        async def create_value(value: int, request_key: uuid.UUID | None = None) -> SampleResponse:
            return SampleResponse(value=value)

        result = await create_value(11, request_key=request_key)

        assert result == SampleResponse(value=11)
        assert cache.store[request_key] == {
            "status": "success",
            "status_code": 200,
            "response": {"value": 11},
            "error": None,
        }
