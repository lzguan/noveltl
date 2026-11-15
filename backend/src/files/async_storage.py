from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Protocol

from aiobotocore.session import get_session
from botocore.config import Config

from src.files.storage import _DEFAULT_CHUNK_SIZE, _DEFAULT_MULTIPART_PART_SIZE, UploadResult, _read_etag


class AsyncObjectWriter(Protocol):
    @property
    def result(self) -> UploadResult: ...

    async def write(self, data: str | bytes) -> int: ...


class AsyncObjectStore(Protocol):
    def create(
        self,
        key: str,
        *,
        content_type: str,
        content_encoding: str | None = None,
    ) -> AbstractAsyncContextManager[AsyncObjectWriter]: ...

    def fetch(self, key: str, *, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> AsyncIterator[bytes]: ...


class _AsyncMultipartObjectWriter:
    def __init__(
        self,
        *,
        client: Any,
        bucket: str,
        key: str,
        content_type: str,
        content_encoding: str | None,
        part_size: int,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._key = key
        self._content_type = content_type
        self._content_encoding = content_encoding
        self._part_size = part_size
        self._buffer = bytearray()
        self._upload_id: str | None = None
        self._parts: list[dict[str, Any]] = []
        self._closed = False
        self._result: UploadResult | None = None

    @property
    def result(self) -> UploadResult:
        if self._result is None:
            raise RuntimeError("upload result is available only after the create context exits successfully")
        return self._result

    async def write(self, data: str | bytes) -> int:
        if self._closed:
            raise ValueError("cannot write to a closed object")

        encoded = data.encode("utf-8") if isinstance(data, str) else data
        offset = 0
        while offset < len(encoded):
            remaining = self._part_size - len(self._buffer)
            next_offset = offset + remaining
            self._buffer.extend(encoded[offset:next_offset])
            offset = next_offset
            if len(self._buffer) == self._part_size:
                await self._upload_part()
        return len(encoded)

    async def complete(self) -> None:
        if self._closed:
            raise ValueError("object is already closed")
        self._closed = True

        if self._upload_id is None:
            response = await self._client.put_object(
                Bucket=self._bucket,
                Key=self._key,
                Body=bytes(self._buffer),
                **self._content_headers(),
            )
        else:
            if self._buffer:
                await self._upload_part()
            response = await self._client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=self._key,
                UploadId=self._upload_id,
                MultipartUpload={"Parts": self._parts},
            )

        self._result = UploadResult(key=self._key, etag=_read_etag(response))
        self._buffer.clear()

    async def abort(self) -> None:
        self._closed = True
        self._buffer.clear()
        if self._upload_id is not None:
            await self._client.abort_multipart_upload(
                Bucket=self._bucket,
                Key=self._key,
                UploadId=self._upload_id,
            )

    async def _upload_part(self) -> None:
        if self._upload_id is None:
            response = await self._client.create_multipart_upload(
                Bucket=self._bucket,
                Key=self._key,
                **self._content_headers(),
            )
            self._upload_id = response["UploadId"]

        part_number = len(self._parts) + 1
        response = await self._client.upload_part(
            Bucket=self._bucket,
            Key=self._key,
            UploadId=self._upload_id,
            PartNumber=part_number,
            Body=bytes(self._buffer),
        )
        self._parts.append({"PartNumber": part_number, "ETag": response["ETag"]})
        self._buffer.clear()

    def _content_headers(self) -> dict[str, str]:
        headers = {"ContentType": self._content_type}
        if self._content_encoding is not None:
            headers["ContentEncoding"] = self._content_encoding
        return headers


class AioS3ObjectStore:
    def __init__(
        self,
        *,
        endpoint_url: str | None,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        config: Config,
        multipart_part_size: int = _DEFAULT_MULTIPART_PART_SIZE,
    ) -> None:
        if multipart_part_size < 5 * 1024 * 1024:
            raise ValueError("multipart_part_size must be at least 5 MiB")
        # The session is not tied to an event loop; each operation opens its own client,
        # which is, so the store works from any loop.
        self._session = get_session()
        self._client_options: dict[str, Any] = {
            "endpoint_url": endpoint_url,
            "region_name": region,
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "config": config,
        }
        self._bucket = bucket
        self._multipart_part_size = multipart_part_size

    def _client(self) -> AbstractAsyncContextManager[Any]:
        return self._session.create_client("s3", **self._client_options)

    @asynccontextmanager
    async def create(
        self,
        key: str,
        *,
        content_type: str,
        content_encoding: str | None = None,
    ) -> AsyncGenerator[AsyncObjectWriter]:
        async with self._client() as client:
            writer = _AsyncMultipartObjectWriter(
                client=client,
                bucket=self._bucket,
                key=key,
                content_type=content_type,
                content_encoding=content_encoding,
                part_size=self._multipart_part_size,
            )
            try:
                yield writer
                await writer.complete()
            except BaseException:
                try:
                    await writer.abort()
                except Exception:
                    pass
                raise

    async def fetch(
        self,
        key: str,
        *,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
    ) -> AsyncGenerator[bytes]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        async with self._client() as client:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            async with response["Body"] as body:
                while chunk := await body.read(chunk_size):
                    yield chunk
