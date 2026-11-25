import hashlib

from fastapi import Response


def make_etag(material: str) -> str:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f'"{digest}"'


def _strip_weak_prefix(tag: str) -> str:
    stripped = tag.strip()
    if stripped.startswith(("W/", "w/")):
        return stripped[2:].strip()
    return stripped


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    target = _strip_weak_prefix(etag)
    for candidate in if_none_match.split(","):
        cleaned = _strip_weak_prefix(candidate)
        if cleaned == "*" or cleaned == target:
            return True
    return False


def apply_cache_headers(response: Response, etag: str, cache_control: str) -> None:
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = cache_control


def not_modified_response(etag: str, cache_control: str) -> Response:
    return Response(
        status_code=304,
        headers={
            "ETag": etag,
            "Cache-Control": cache_control,
        },
    )
