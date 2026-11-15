import asyncio
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Any

import pytest
from botocore.config import Config

from src.files.async_storage import AioS3ObjectStore

_MINIMUM_PART_SIZE = 5 * 1024 * 1024


class AsyncBody:
    def __init__(self, content: bytes) -> None:
        self.stream = BytesIO(content)
        self.closed = False

    async def read(self, size: int) -> bytes:
        return self.stream.read(size)

    async def __aenter__(self) -> AsyncBody:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed = True


class RecordingAsyncS3Client:
    def __init__(self) -> None:
        self.puts: list[dict[str, Any]] = []
        self.created_uploads: list[dict[str, Any]] = []
        self.uploaded_parts: list[dict[str, Any]] = []
        self.completed_uploads: list[dict[str, Any]] = []
        self.aborted_uploads: list[dict[str, Any]] = []
        self.objects: dict[tuple[str, str], bytes] = {}
        self.response_body: AsyncBody | None = None
        self.open_clients = 0

    async def put_object(self, **kwargs: Any) -> dict[str, str]:
        self.puts.append(kwargs)
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]
        return {"ETag": '"small-etag"'}

    async def create_multipart_upload(self, **kwargs: Any) -> dict[str, str]:
        self.created_uploads.append(kwargs)
        return {"UploadId": "upload-1"}

    async def upload_part(self, **kwargs: Any) -> dict[str, str]:
        self.uploaded_parts.append(kwargs)
        return {"ETag": f'"part-{kwargs["PartNumber"]}"'}

    async def complete_multipart_upload(self, **kwargs: Any) -> dict[str, str]:
        self.completed_uploads.append(kwargs)
        return {"ETag": '"multipart-etag"'}

    async def abort_multipart_upload(self, **kwargs: Any) -> None:
        self.aborted_uploads.append(kwargs)

    async def get_object(self, **kwargs: Any) -> dict[str, AsyncBody]:
        self.response_body = AsyncBody(self.objects[(kwargs["Bucket"], kwargs["Key"])])
        return {"Body": self.response_body}


@pytest.fixture
def object_store() -> tuple[AioS3ObjectStore, RecordingAsyncS3Client]:
    client = RecordingAsyncS3Client()
    store = AioS3ObjectStore(
        endpoint_url="http://garage:3900",
        region="garage",
        access_key_id="access-key",
        secret_access_key="secret-key",
        bucket="noveltl",
        config=Config(s3={"addressing_style": "path"}),
        multipart_part_size=_MINIMUM_PART_SIZE,
    )

    @asynccontextmanager
    async def make_client():
        client.open_clients += 1
        try:
            yield client
        finally:
            client.open_clients -= 1

    # Replace only the S3 boundary; the store's session would otherwise build a real client.
    store._client = make_client
    return store, client


def test_create_uses_put_object_below_multipart_threshold(
    object_store: tuple[AioS3ObjectStore, RecordingAsyncS3Client],
) -> None:
    store, client = object_store

    async def run():
        async with store.create("translations/input.jsonl", content_type="application/jsonl") as output:
            assert await output.write('{"id":1}') == 8
            assert await output.write(b"\n") == 1
            with pytest.raises(RuntimeError, match="only after"):
                _ = output.result
        return output

    output = asyncio.run(run())

    assert client.puts == [
        {
            "Bucket": "noveltl",
            "Key": "translations/input.jsonl",
            "Body": b'{"id":1}\n',
            "ContentType": "application/jsonl",
        }
    ]
    assert client.created_uploads == []
    assert output.result.key == "translations/input.jsonl" and output.result.etag == "small-etag"
    assert client.open_clients == 0


def test_create_streams_full_buffers_as_multipart_parts(
    object_store: tuple[AioS3ObjectStore, RecordingAsyncS3Client],
) -> None:
    store, client = object_store
    first_write = b"a" * (_MINIMUM_PART_SIZE - 1)

    async def run():
        async with store.create(
            "translations/input.jsonl", content_type="application/jsonl", content_encoding="gzip"
        ) as output:
            await output.write(first_write)
            assert client.uploaded_parts == []
            await output.write(b"bc")
        return output

    output = asyncio.run(run())

    assert client.created_uploads == [
        {
            "Bucket": "noveltl",
            "Key": "translations/input.jsonl",
            "ContentType": "application/jsonl",
            "ContentEncoding": "gzip",
        }
    ]
    assert [part["Body"] for part in client.uploaded_parts] == [first_write + b"b", b"c"]
    assert [part["PartNumber"] for part in client.uploaded_parts] == [1, 2]
    assert client.completed_uploads[0]["MultipartUpload"] == {
        "Parts": [{"PartNumber": 1, "ETag": '"part-1"'}, {"PartNumber": 2, "ETag": '"part-2"'}]
    }
    assert output.result.etag == "multipart-etag"


def test_create_aborts_started_multipart_upload_when_producer_fails(
    object_store: tuple[AioS3ObjectStore, RecordingAsyncS3Client],
) -> None:
    store, client = object_store

    async def run() -> None:
        async with store.create("translations/input.jsonl", content_type="application/jsonl") as output:
            await output.write(b"a" * _MINIMUM_PART_SIZE)
            raise RuntimeError("batch generation failed")

    with pytest.raises(RuntimeError, match="batch generation failed"):
        asyncio.run(run())

    assert client.completed_uploads == []
    assert client.aborted_uploads == [{"Bucket": "noveltl", "Key": "translations/input.jsonl", "UploadId": "upload-1"}]
    assert client.open_clients == 0


def test_fetch_closes_response_when_consumer_stops_early(
    object_store: tuple[AioS3ObjectStore, RecordingAsyncS3Client],
) -> None:
    store, client = object_store
    client.objects[("noveltl", "translations/output.jsonl")] = b"abcdef"

    async def run() -> bytes:
        chunks = store.fetch("translations/output.jsonl", chunk_size=2)
        try:
            return await anext(chunks)
        finally:
            await chunks.aclose()

    assert asyncio.run(run()) == b"ab"
    assert client.response_body is not None and client.response_body.closed
    assert client.open_clients == 0
