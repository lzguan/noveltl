from urllib.parse import quote

import httpx2
from pydantic import ValidationError

from src.config import publishing_settings
from src.publishing.constants import READER_PROTOCOL_VERSION
from src.publishing.exceptions import TargetConnectionException
from src.publishing.reader_schemas import (
    IngestChapterUpsertItem,
    IngestHealthResponse,
    IngestNovelStatusResponse,
    IngestNovelSyncRequest,
    IngestNovelSyncResponse,
    IngestNovelUpsertRequest,
)


def _format_http_error(response: httpx2.Response) -> str:
    detail = response.text.strip()[:512]
    if detail:
        return f"Reader returned HTTP {response.status_code}: {detail}"
    return f"Reader returned HTTP {response.status_code}."


class ReaderClient:
    def __init__(
        self,
        *,
        transport: httpx2.AsyncBaseTransport | None = None,
        timeout: float | None = None,
    ) -> None:
        self.transport = transport
        self.timeout = timeout

    def _client(self, api_base_url: str, api_key: str) -> httpx2.AsyncClient:
        effective_timeout = (
            self.timeout if self.timeout is not None else publishing_settings.PUBLISH_HTTP_TIMEOUT_SECONDS
        )
        return httpx2.AsyncClient(
            base_url=api_base_url.rstrip("/") + "/",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=effective_timeout,
            transport=self.transport,
            follow_redirects=False,
        )

    async def check_health(self, api_base_url: str, api_key: str) -> IngestHealthResponse:
        try:
            async with self._client(api_base_url, api_key) as client:
                response = await client.get("ingest/health")
        except httpx2.HTTPError as e:
            raise TargetConnectionException(f"Failed to reach Reader target: {e}") from e

        if response.status_code >= 300:
            raise TargetConnectionException(_format_http_error(response), status_code=response.status_code)

        try:
            health = IngestHealthResponse.model_validate_json(response.content)
        except ValidationError as e:
            raise TargetConnectionException("Reader returned an invalid health response.") from e

        if not health.ok:
            raise TargetConnectionException("Reader health check reported ok=false.")
        if health.protocol_version != READER_PROTOCOL_VERSION:
            raise TargetConnectionException(
                f"Unsupported Reader protocol version: {health.protocol_version} (expected {READER_PROTOCOL_VERSION})."
            )
        return health

    async def get_novel_status(self, api_base_url: str, api_key: str, external_id: str) -> IngestNovelStatusResponse:
        path = f"ingest/novels/{quote(external_id, safe='')}/status"
        try:
            async with self._client(api_base_url, api_key) as client:
                response = await client.get(path)
        except httpx2.HTTPError as e:
            raise TargetConnectionException(f"Failed to query Reader novel status: {e}") from e

        if response.status_code >= 300:
            raise TargetConnectionException(_format_http_error(response), status_code=response.status_code)

        try:
            return IngestNovelStatusResponse.model_validate_json(response.content)
        except ValidationError as e:
            raise TargetConnectionException("Reader returned an invalid novel status response.") from e

    async def sync_novel(
        self,
        api_base_url: str,
        api_key: str,
        external_id: str,
        novel: IngestNovelUpsertRequest | None,
        upserts: list[IngestChapterUpsertItem],
    ) -> IngestNovelSyncResponse:
        path = f"ingest/novels/{quote(external_id, safe='')}/sync"
        payload = IngestNovelSyncRequest(novel=novel, upserts=upserts).model_dump(by_alias=True, mode="json")
        try:
            async with self._client(api_base_url, api_key) as client:
                response = await client.post(path, json=payload)
        except httpx2.HTTPError as e:
            raise TargetConnectionException(f"Failed to sync novel to Reader: {e}") from e

        if response.status_code >= 300:
            raise TargetConnectionException(_format_http_error(response), status_code=response.status_code)

        try:
            return IngestNovelSyncResponse.model_validate_json(response.content)
        except ValidationError as e:
            raise TargetConnectionException("Reader returned an invalid sync response.") from e
