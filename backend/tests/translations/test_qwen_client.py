import json
from collections.abc import Iterator

import httpx2
import pytest
from openai import InternalServerError, OpenAI

from src.translations.clients.qwen_client import QwenClient


class UploadChunks(Iterator[bytes]):
    def __init__(self) -> None:
        self.chunks = iter([b'{"custom_id":', b'"chapter-1"}\n'])
        self.closed = False

    def __next__(self) -> bytes:
        return next(self.chunks)

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("upload_status", [200, 500])
def test_upload_stream_is_not_replayed_and_is_closed(upload_status: int) -> None:
    # Submission workers rely on upload failures propagating without an SDK
    # replay of an exhausted stream. Keep SDK/multipart behavior real and replace
    # only HTTP transport, avoiding paid calls and forcing a retryable failure.
    requests: list[httpx2.Request] = []
    chunks = UploadChunks()

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.url.path == "/files":
            assert b'filename="input.jsonl"' in request.content
            assert b'{"custom_id":"chapter-1"}\n' in request.content
            if upload_status == 500:
                return httpx2.Response(500, json={"error": {"message": "temporary failure"}})
            return httpx2.Response(
                200,
                json={
                    "id": "file-1",
                    "bytes": 26,
                    "created_at": 1,
                    "filename": "input.jsonl",
                    "object": "file",
                    "purpose": "batch",
                },
            )
        assert request.url.path == "/batches"
        assert chunks.closed
        assert json.loads(request.content)["input_file_id"] == "file-1"
        return httpx2.Response(200, json={"id": "batch-1", "object": "batch", "status": "validating"})

    client = QwenClient(api_key="test-key", base_url="https://example.invalid")
    client.client.close()
    with OpenAI(
        api_key="test-key",
        base_url="https://example.invalid",
        max_retries=2,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handle)),
    ) as sdk:
        client.client = sdk
        if upload_status == 500:
            with pytest.raises(InternalServerError):
                client.create_batch_job(chunks)
            assert [request.url.path for request in requests] == ["/files"]
        else:
            assert client.create_batch_job(chunks) == "batch-1"
            assert [request.url.path for request in requests] == ["/files", "/batches"]
        assert sdk.max_retries == 2
    assert chunks.closed
