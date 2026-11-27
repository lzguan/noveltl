import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from src.auth import bearer_scheme
from src.config import reader_settings

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_MAXMEM = 64 * 1024 * 1024
SALT_BYTES = 16


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode("ascii"))


def hash_admin_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=SCRYPT_MAXMEM,
        dklen=SCRYPT_DKLEN,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(derived).decode("ascii")
    return f"scrypt${salt_b64}${hash_b64}"


def verify_admin_password(password: str, stored_hash: str) -> bool:
    parts = stored_hash.split("$")
    if len(parts) != 3 or parts[0] != "scrypt":
        return False
    try:
        salt = base64.b64decode(parts[1], validate=True)
        expected = base64.b64decode(parts[2], validate=True)
    except ValueError:
        return False
    if not salt or not expected:
        return False
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=SCRYPT_MAXMEM,
        dklen=len(expected),
    )
    return hmac.compare_digest(derived, expected)


def verify_admin_credentials(username: str, password: str) -> bool:
    username_ok = hmac.compare_digest(
        username.encode("utf-8"),
        reader_settings.READER_ADMIN_USERNAME.encode("utf-8"),
    )
    password_ok = verify_admin_password(password, reader_settings.READER_ADMIN_PASSWORD_HASH)
    return username_ok and password_ok


def create_admin_token(username: str) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(seconds=reader_settings.READER_ADMIN_TOKEN_TTL_SECONDS)
    payload_bytes = json.dumps(
        {"sub": username, "exp": int(expires_at.timestamp())},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)
    sig = hmac.new(
        reader_settings.READER_ADMIN_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_b64}.{_b64url_encode(sig)}", expires_at


def verify_admin_token(token: str) -> str | None:
    secret = reader_settings.READER_ADMIN_SECRET
    if not secret:
        return None

    parts = token.split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    payload_b64, sig_b64 = parts

    expected_sig = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        actual_sig = _b64url_decode(sig_b64)
    except ValueError:
        return None
    if not hmac.compare_digest(actual_sig, expected_sig):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None

    sub = payload.get("sub")
    exp = payload.get("exp")
    if not isinstance(sub, str) or not sub:
        return None
    if not isinstance(exp, int) or isinstance(exp, bool):
        return None
    if exp <= int(datetime.now(UTC).timestamp()):
        return None
    if not hmac.compare_digest(sub.encode("utf-8"), reader_settings.READER_ADMIN_USERNAME.encode("utf-8")):
        return None
    return sub


async def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if not reader_settings.is_admin_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reader admin is not configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = verify_admin_token(credentials.credentials)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username
