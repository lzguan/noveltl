from io import BytesIO
from typing import Any

import pytest
from botocore.config import Config

from src.files.storage import S3ObjectStore

_MINIMUM_PART_SIZE = 5 * 1024 * 1024


class RecordingS3Client:
    def __init__(self) -> None:
        self.puts: list[dict[str, Any]] = []
        self.created_uploads: list[dict[str, Any]] = []
        self.uploaded_parts: list[dict[str, Any]] = []
        self.completed_uploads: list[dict[str, Any]] = []
        self.aborted_uploads: list[dict[str, Any]] = []
        self.objects: dict[tuple[str, str], bytes] = {}
        self.response_body: BytesIO | None = None

    def put_object(self, **kwargs: Any) -> dict[str, str]:
        self.puts.append(kwargs)
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]
        return {"ETag": '"small-etag"'}

    def create_multipart_upload(self, **kwargs: Any) -> dict[str, str]:
        self.created_uploads.append(kwargs)
        return {"UploadId": "upload-1"}

    def upload_part(self, **kwargs: Any) -> dict[str, str]:
        self.uploaded_parts.append(kwargs)
        return {"ETag": f'"part-{kwargs["PartNumber"]}"'}

    def complete_multipart_upload(self, **kwargs: Any) -> dict[str, str]:
        self.completed_uploads.append(kwargs)
        return {"ETag": '"multipart-etag"'}

    def abort_multipart_upload(self, **kwargs: Any) -> None:
        self.aborted_uploads.append(kwargs)

    def get_object(self, **kwargs: Any) -> dict[str, BytesIO]:
        self.response_body = BytesIO(self.objects[(kwargs["Bucket"], kwargs["Key"])])
        return {"Body": self.response_body}


@pytest.fixture
def object_store(monkeypatch: pytest.MonkeyPatch) -> tuple[S3ObjectStore, RecordingS3Client]:
    client = RecordingS3Client()

    def make_client(*args: Any, **kwargs: Any) -> RecordingS3Client:
        return client

    monkeypatch.setattr("src.files.storage.boto3.client", make_client)
    store = S3ObjectStore(
        endpoint_url="http://garage:3900",
        region="garage",
        access_key_id="access-key",
        secret_access_key="secret-key",
        bucket="noveltl",
        config=Config(s3={"addressing_style": "path"}),
        multipart_part_size=_MINIMUM_PART_SIZE,
    )
    return store, client


def test_create_uses_put_object_below_multipart_threshold(
    object_store: tuple[S3ObjectStore, RecordingS3Client],
) -> None:
    store, client = object_store

    with store.create("translations/input.jsonl", content_type="application/jsonl") as output:
        assert output.write('{"id":1}') == 8
        assert output.write(b"\n") == 1
        with pytest.raises(RuntimeError, match="only after"):
            _ = output.result

    assert client.puts == [
        {
            "Bucket": "noveltl",
            "Key": "translations/input.jsonl",
            "Body": b'{"id":1}\n',
            "ContentType": "application/jsonl",
        }
    ]
    assert client.created_uploads == []
    assert output.result.key == "translations/input.jsonl"
    assert output.result.etag == "small-etag"


def test_create_streams_full_buffers_as_multipart_parts(
    object_store: tuple[S3ObjectStore, RecordingS3Client],
) -> None:
    store, client = object_store
    first_write = b"a" * (_MINIMUM_PART_SIZE - 1)

    with store.create(
        "translations/input.jsonl",
        content_type="application/jsonl",
        content_encoding="gzip",
    ) as output:
        output.write(first_write)
        assert client.uploaded_parts == []
        output.write(b"bc")

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
        "Parts": [
            {"PartNumber": 1, "ETag": '"part-1"'},
            {"PartNumber": 2, "ETag": '"part-2"'},
        ]
    }
    assert output.result.etag == "multipart-etag"


def test_create_aborts_started_multipart_upload_when_producer_fails(
    object_store: tuple[S3ObjectStore, RecordingS3Client],
) -> None:
    store, client = object_store

    with pytest.raises(RuntimeError, match="batch generation failed"):
        with store.create("translations/input.jsonl", content_type="application/jsonl") as output:
            output.write(b"a" * _MINIMUM_PART_SIZE)
            raise RuntimeError("batch generation failed")

    assert client.completed_uploads == []
    assert client.aborted_uploads == [
        {
            "Bucket": "noveltl",
            "Key": "translations/input.jsonl",
            "UploadId": "upload-1",
        }
    ]


def test_fetch_closes_response_when_consumer_stops_early(
    object_store: tuple[S3ObjectStore, RecordingS3Client],
) -> None:
    store, client = object_store
    client.objects[("noveltl", "translations/output.jsonl")] = b"abcdef"

    chunks = store.fetch("translations/output.jsonl", chunk_size=2)
    assert next(chunks) == b"ab"
    chunks.close()

    assert client.response_body is not None
    assert client.response_body.closed
