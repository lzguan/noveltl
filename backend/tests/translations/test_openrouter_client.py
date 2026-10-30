"""Translation workers need durable batch handles and codec-compatible results.

Keep HTTP serialization, the client, and the codec real. Replace the paid
provider's HTTP boundary to exercise delayed results, failures, and fresh-worker
retrieval deterministically; these tests do not establish live model behavior.
"""

import json
import re
from collections.abc import Callable, Generator
from contextlib import contextmanager
from uuid import UUID

import httpx2
import pytest

from src.translations.clients.batch_jobs import (
    BatchJobComplete,
    BatchJobFailed,
    BatchJobId,
    BatchJobPending,
    BatchOutputId,
)
from src.translations.clients.openrouter_client import OpenRouterClient
from src.translations.codecs.batch_lines import (
    BatchItem,
    BatchItemFailure,
    BatchItemSuccess,
    InferenceMessage,
    InferenceRequest,
)
from src.translations.codecs.registry import get_codec
from src.translations.types import TranslationDataKey

MODEL = "deepseek/deepseek-v4.1-flash"


@contextmanager
def client_for(handler: Callable[[httpx2.Request], httpx2.Response]) -> Generator[OpenRouterClient, None, None]:
    client = OpenRouterClient(api_key="test-key", base_url="https://example.invalid/api/v1")
    client.client.close()
    with httpx2.Client(
        base_url="https://example.invalid/api/v1/",
        headers={"Authorization": "Bearer test-key", "Content-Type": "application/json"},
        transport=httpx2.MockTransport(handler),
    ) as transport:
        client.client = transport
        yield client


def request_line(key: TranslationDataKey, *, model: str = MODEL) -> bytes:
    return get_codec(MODEL).encode_request(
        BatchItem(
            key=key,
            request=InferenceRequest(
                model=model,
                messages=(InferenceMessage(role="user", content="第一章\nTranslate this."),),
                temperature=0.0,
                max_output_tokens=100,
            ),
        )
    )


def test_submit_poll_and_fresh_worker_output_preserve_codec_contract() -> None:
    keys = [TranslationDataKey(UUID(int=1), name) for name in ("chapter", "memories")]
    lines = [request_line(key) for key in keys]
    custom_ids = [json.loads(line)["custom_id"] for line in lines]
    results = [
        {
            "custom_id": custom_ids[1],
            "response": None,
            "error": {
                "type": "invalid_request_error",
                "message": "Provider rejected this request",
                "param": "max_tokens",
            },
        },
        {
            "custom_id": custom_ids[0],
            "response": {
                "status_code": 200,
                "request_id": "provider-request-1",
                "body": {
                    "id": "generation-1",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "Chapter 一\nText"},
                        }
                    ],
                },
            },
            "error": None,
        },
    ]
    reads = 0

    def handle(request: httpx2.Request) -> httpx2.Response:
        nonlocal reads
        assert request.headers["Authorization"] == "Bearer test-key"
        if request.method == "POST":
            assert request.url.path == "/api/v1/batches"
            payload = json.loads(request.content)
            assert all(len(item["custom_id"]) <= 64 for item in payload["requests"])
            assert all(re.fullmatch(r"[a-z0-9_-]+", item["custom_id"]) for item in payload["requests"])
            assert len({item["custom_id"] for item in payload["requests"]}) == len(keys)
            assert list(payload) == ["endpoint", "model", "completion_window", "requests"]
            assert payload == {
                "endpoint": "/v1/chat/completions",
                "model": MODEL,
                "completion_window": "24h",
                "requests": [
                    {"custom_id": custom_id, "body": json.loads(line)["body"]}
                    for custom_id, line in zip(custom_ids, lines, strict=True)
                ],
            }
            return httpx2.Response(202, json={"id": "batch-1", "status": "validating", "results": None})
        assert request.url.path == "/api/v1/batches/batch-1"
        reads += 1
        return httpx2.Response(
            200, json={"id": "batch-1", "status": "completed", "results": None if reads == 1 else results}
        )

    # Include arbitrary chunk boundaries and CRLF; the input is single-use.
    content = b"".join(lines).replace(b"\n", b"\r\n")
    with client_for(handle) as submitter:
        job_id = submitter.create_batch_job(iter((content[:13], content[13:])))
    with client_for(handle) as poller:
        assert poller.poll_batch_job(job_id) == BatchJobPending()
        finished = poller.poll_batch_job(job_id)
        assert finished == BatchJobComplete(output_id=BatchOutputId("batch-1"))
    codec = get_codec(MODEL)
    with client_for(handle) as finalizer:
        for _ in range(2):
            output = list(finalizer.fetch_batch_output(BatchOutputId("batch-1")))
            assert all(line.endswith(b"\n") and line.count(b"\n") == 1 for line in output)
            assert [codec.decode_result(line) for line in output] == [
                BatchItemFailure(key=keys[1], error="Provider rejected this request", code=None),
                BatchItemSuccess(key=keys[0], text="Chapter 一\nText", finish_reason="stop"),
            ]
    assert reads == 4


@pytest.mark.parametrize("status", ["validating", "in_progress", "finalizing", "cancelling"])
def test_nonterminal_batches_remain_pending(status: str) -> None:
    with client_for(lambda _: httpx2.Response(200, json={"id": "batch-1", "status": status})) as client:
        assert client.poll_batch_job(BatchJobId("batch-1")) == BatchJobPending()


@pytest.mark.parametrize("status", ["failed", "expired", "cancelled"])
def test_terminal_failure_preserves_status_and_provider_reason(status: str) -> None:
    with client_for(
        lambda _: httpx2.Response(
            200, json={"id": "batch-1", "status": status, "error": {"message": "Provider reason"}}
        )
    ) as client:
        assert client.poll_batch_job(BatchJobId("batch-1")) == BatchJobFailed(
            error=f"OpenRouter batch batch-1 {status}: Provider reason"
        )


@pytest.mark.parametrize("status,results", [("in_progress", None), ("failed", []), ("completed", None)])
def test_unavailable_results_raise_instead_of_emitting_an_empty_output(status: str, results: object) -> None:
    with client_for(
        lambda _: httpx2.Response(200, json={"id": "batch-1", "status": status, "results": results})
    ) as client:
        with pytest.raises(ValueError, match="results are not available"):
            list(client.fetch_batch_output(BatchOutputId("batch-1")))


@pytest.mark.parametrize("operation", ["submit", "poll", "fetch"])
@pytest.mark.parametrize("status", [422, 500])
def test_http_failure_propagates_without_replaying_submission(operation: str, status: int) -> None:
    requests: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(status, json={"error": {"message": "Provider failure detail"}})

    with client_for(handle) as client, pytest.raises(httpx2.HTTPStatusError, match="Provider failure detail") as exc:
        if operation == "submit":
            client.create_batch_job(iter((request_line(TranslationDataKey(UUID(int=1), "chapter")),)))
        elif operation == "poll":
            client.poll_batch_job(BatchJobId("batch-1"))
        else:
            list(client.fetch_batch_output(BatchOutputId("batch-1")))
    assert exc.value.response.status_code == status
    assert len(requests) == 1


@pytest.mark.parametrize(
    "response",
    [
        {"id": "", "status": "completed", "results": []},
        {"id": "another-batch", "status": "completed", "results": []},
        {"id": "batch-1", "status": "unknown"},
        {"id": "batch-1", "status": "completed", "results": {}},
    ],
)
def test_invalid_poll_responses_raise(response: dict[str, object]) -> None:
    with client_for(lambda _: httpx2.Response(200, json=response)) as client, pytest.raises(ValueError):
        client.poll_batch_job(BatchJobId("batch-1"))


@pytest.mark.parametrize(
    "invalid", ["empty", "malformed", "mixed-models", "duplicate-keys", "wrong-endpoint", "long-id", "invalid-id"]
)
def test_invalid_submission_cannot_produce_a_job_handle(invalid: str) -> None:
    key = TranslationDataKey(UUID(int=1), "chapter")
    line = request_line(key)
    content = {
        "empty": b"",
        "malformed": b"not json\n",
        "mixed-models": line + request_line(TranslationDataKey(UUID(int=2), "chapter"), model="another-model"),
        "duplicate-keys": line + line,
        "wrong-endpoint": line.replace(b"/v1/chat/completions", b"/v1/responses"),
        "long-id": json.dumps({**json.loads(line), "custom_id": "a" * 65}).encode() + b"\n",
        "invalid-id": json.dumps({**json.loads(line), "custom_id": '["chapter","memories"]'}).encode() + b"\n",
    }[invalid]
    with client_for(lambda _: httpx2.Response(202, json={"id": "batch-1", "status": "validating"})) as client:
        with pytest.raises(ValueError):
            client.create_batch_job(iter((content,)))
