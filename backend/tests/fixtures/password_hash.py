import pytest
from pwdlib import PasswordHash
from typing import Protocol

class Hash(Protocol):
    def hash(self, password : str | bytes, *args, **kwargs) -> str:
        ...

    def verify(self, password : str | bytes, hash : str | bytes) -> bool:
        ...

@pytest.fixture 
def recommended_hash() -> Hash:
    return PasswordHash.recommended()

class NoHash(Hash):
    def hash(self, password: str | bytes, *args, **kwargs) -> str:
        return str(password)
    
    def verify(self, password: str | bytes, hash: str | bytes) -> bool:
        return str(password) == str(hash)

@pytest.fixture
def no_hash() -> Hash:
    return NoHash()