import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_db
from src.models import ReaderPartner, ReaderPartnerKey

KEY_PREFIX_LENGTH = 16
bearer_scheme = HTTPBearer(auto_error=False)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    raw_key = f"rapi_{secrets.token_urlsafe(32)}"
    return raw_key, raw_key[:KEY_PREFIX_LENGTH], hash_api_key(raw_key)


async def require_partner(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> ReaderPartner:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key_hash = hash_api_key(credentials.credentials)
    stmt = (
        select(ReaderPartner)
        .join(ReaderPartnerKey, ReaderPartnerKey.partner_id == ReaderPartner.partner_id)
        .where(ReaderPartnerKey.key_hash == key_hash, ReaderPartnerKey.revoked_at.is_(None))
    )
    partner = (await db.execute(stmt)).scalar_one_or_none()
    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return partner
