import asyncio
import base64
import hashlib
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

from cryptography.fernet import Fernet, InvalidToken

from src.config import publishing_settings
from src.publishing.exceptions import (
    InvalidTargetUrlException,
    KeyDecryptionException,
    PublishingNotConfiguredException,
)

type IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _get_fernet() -> Fernet:
    secret = publishing_settings.PUBLISH_KEY_ENCRYPTION_SECRET.strip()
    if not secret:
        raise PublishingNotConfiguredException("PUBLISH_KEY_ENCRYPTION_SECRET is not configured.")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_api_key(api_key: str) -> str:
    return _get_fernet().encrypt(api_key.encode("utf-8")).decode("ascii")


def decrypt_api_key(encrypted_api_key: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted_api_key.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise KeyDecryptionException("Failed to decrypt target API key.") from e


def extract_key_prefix(api_key: str) -> str:
    stripped = api_key.strip()
    if len(stripped) >= 24:
        return stripped[:16]
    if len(stripped) <= 8:
        return stripped[: max(1, len(stripped) // 2)]
    return stripped[:8]


def _is_blocked_ip(ip: IPAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        if _is_blocked_ip(ip.ipv4_mapped):
            return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _parse_ip(raw_host: str) -> IPAddress | None:
    host = raw_host.split("%", 1)[0]
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


async def validate_target_url(raw_url: str) -> str:
    url = raw_url.strip()
    if not url:
        raise InvalidTargetUrlException("Target URL must not be empty.")

    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise InvalidTargetUrlException("Target URL must use http or https.")
    if not parsed.hostname:
        raise InvalidTargetUrlException("Target URL must include a host.")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidTargetUrlException("Target URL must not contain embedded credentials.")
    if parsed.query or parsed.fragment:
        raise InvalidTargetUrlException("Target URL must not contain query parameters or fragments.")
    try:
        port = parsed.port
    except ValueError as e:
        raise InvalidTargetUrlException("Target URL has an invalid port.") from e

    host = parsed.hostname
    if not publishing_settings.ALLOW_PRIVATE_PUBLISH_TARGETS:
        literal_ip = _parse_ip(host)
        if literal_ip is not None:
            if _is_blocked_ip(literal_ip):
                raise InvalidTargetUrlException("Target URL resolves to a disallowed IP address.")
        else:
            lookup_port = port if port is not None else (443 if scheme == "https" else 80)
            try:
                addr_infos = await asyncio.to_thread(
                    socket.getaddrinfo, host, lookup_port, type=socket.SOCK_STREAM
                )
            except OSError as e:
                raise InvalidTargetUrlException(f"Could not resolve target host: {host}") from e
            if not addr_infos:
                raise InvalidTargetUrlException(f"Could not resolve target host: {host}")
            for _, _, _, _, sockaddr in addr_infos:
                resolved_ip = _parse_ip(str(sockaddr[0]))
                if resolved_ip is None or _is_blocked_ip(resolved_ip):
                    raise InvalidTargetUrlException("Target URL resolves to a disallowed IP address.")

    normalized_path = parsed.path.rstrip("/")
    return urlunsplit((scheme, parsed.netloc, normalized_path, "", ""))
