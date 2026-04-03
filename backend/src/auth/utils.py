from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from .config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY

password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Wrapper for verifying that a plain password gets hashed to the hashed password.

    Args:
        plain_password: A plain password.
        hashed_password: The candidate hashed password.
    """
    return password_hash.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """
    Hashes a password.

    Args:
        password: Password to hash.
    """
    return password_hash.hash(password)


def create_access_token(data: dict[Any, Any], expires_delta: timedelta) -> str:
    """
    Create a JSON web token for the data in data that expires in time expires_delta.

    Args:
        data: Dict to serialize.
        expires_delta: Time until expiry, as a timedelta object.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)  # type: ignore
    return encoded_jwt
