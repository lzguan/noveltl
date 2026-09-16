from collections.abc import Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

import boto3
from botocore.config import Config

_DEFAULT_CHUNK_SIZE = 1024 * 1024
_DEFAULT_MULTIPART_PART_SIZE = 8 * 1024 * 1024


@dataclass(frozen=True)
class UploadResult:
    key: str
    etag: str | None


class ObjectWriter(Protocol):
    @property
    def result(self) -> UploadResult: ...

    def write(self, data: str | bytes) -> int: ...


class ObjectStore(Protocol):
    def create(
        self,
        key: str,
        *,
        content_type: str,
        content_encoding: str | None = None,
    ) -> AbstractContextManager[ObjectWriter]: ...

    def fetch(self, key: str, *, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> Iterator[bytes]: ...


class _MultipartObjectWriter:
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

    def write(self, data: str | bytes) -> int:
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
                self._upload_part()
        return len(encoded)

    def complete(self) -> None:
        if self._closed:
            raise ValueError("object is already closed")
        self._closed = True

        if self._upload_id is None:
            response = self._client.put_object(
                Bucket=self._bucket,
                Key=self._key,
                Body=bytes(self._buffer),
                **self._content_headers(),
            )
        else:
            if self._buffer:
                self._upload_part()
            response = self._client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=self._key,
                UploadId=self._upload_id,
                MultipartUpload={"Parts": self._parts},
            )

        self._result = UploadResult(key=self._key, etag=_read_etag(response))
        self._buffer.clear()

    def abort(self) -> None:
        self._closed = True
        self._buffer.clear()
        if self._upload_id is not None:
            self._client.abort_multipart_upload(
                Bucket=self._bucket,
                Key=self._key,
                UploadId=self._upload_id,
            )

    def _upload_part(self) -> None:
        if self._upload_id is None:
            response = self._client.create_multipart_upload(
                Bucket=self._bucket,
                Key=self._key,
                **self._content_headers(),
            )
            self._upload_id = response["UploadId"]

        part_number = len(self._parts) + 1
        response = self._client.upload_part(
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


class S3ObjectStore:
    """Thin streaming wrapper around a boto3 S3 client."""

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
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=config,
        )
        self._bucket = bucket
        self._multipart_part_size = multipart_part_size

    @contextmanager
    def create(
        self,
        key: str,
        *,
        content_type: str,
        content_encoding: str | None = None,
    ) -> Generator[ObjectWriter, None, None]:
        writer = _MultipartObjectWriter(
            client=self._client,
            bucket=self._bucket,
            key=key,
            content_type=content_type,
            content_encoding=content_encoding,
            part_size=self._multipart_part_size,
        )
        try:
            yield writer
            writer.complete()
        except BaseException:
            try:
                writer.abort()
            except Exception:
                pass
            raise

    def fetch(
        self,
        key: str,
        *,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
    ) -> Generator[bytes, None, None]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body = response["Body"]
        try:
            while chunk := body.read(chunk_size):
                yield chunk
        finally:
            body.close()


def _read_etag(response: dict[str, Any]) -> str | None:
    etag = response.get("ETag")
    return etag.strip('"') if isinstance(etag, str) else None
