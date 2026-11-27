from typing import Any, Protocol

import pytest
from pwdlib import PasswordHash


class Hash(Protocol):
    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str: ...

    def verify(self, password: str | bytes, hash: str | bytes) -> bool: ...


class CachedPasswordHash(Hash):
    def __init__(self, inner: PasswordHash) -> None:
        self._inner = inner
        self._cache: dict[str | bytes, str] = {}

    def hash(self, password: str | bytes, *args: Any, **kwargs: Any) -> str:
        if not args and not kwargs:
            cached = self._cache.get(password)
            if cached is not None:
                return cached
            hashed = self._inner.hash(password)
            self._cache[password] = hashed
            return hashed
        return self._inner.hash(password, *args, **kwargs)

    def verify(self, password: str | bytes, hash: str | bytes) -> bool:
        return self._inner.verify(password, hash)


@pytest.fixture(scope="session")
def recommended_hash() -> Hash:
    return CachedPasswordHash(PasswordHash.recommended())


class NoHash(Hash):
    def hash(self, password: str | bytes) -> str:
        return str(password)

    def verify(self, password: str | bytes, hash: str | bytes) -> bool:
        return str(password) == str(hash)


@pytest.fixture
def no_hash() -> Hash:
    return NoHash()
