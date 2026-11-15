import json
from uuid import UUID

import httpx2
from openai import OpenAI
from pydantic import TypeAdapter

from src.translations.clients.batch_jobs import BatchJobComplete, BatchOutputId
from src.translations.clients.sync_client import SyncChatClient
from src.translations.codecs.batch_lines import (
    BatchItem,
    BatchItemFailure,
    BatchItemSuccess,
    InferenceMessage,
    InferenceRequest,
)
from src.translations.codecs.openai_chat import OpenAIChatBatchCodec
from src.translations.types import TranslationDataKey
from tests.files.test_access import MemoryObjectStore

CODEC = OpenAIChatBatchCodec(TypeAdapter(TranslationDataKey), max_tokens_field="max_tokens")


def _line(chapter: int, text: str) -> bytes:
    return CODEC.encode_request(
        BatchItem(
            key=TranslationDataKey(UUID(int=chapter), "chapter"),
            request=InferenceRequest(
                model="qwen-flash-sync",
                messages=(InferenceMessage(role="user", content=text),),
                temperature=None,
                max_output_tokens=64,
            ),
        )
    )


def _completion(text: str) -> dict:
    return {
        "id": "completion",
        "object": "chat.completion",
        "created": 1,
        "model": "qwen-flash",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
    }


def _client(handler, store: MemoryObjectStore, *, max_retries: int = 0) -> SyncChatClient:
    sdk = OpenAI(
        api_key="test-key",
        base_url="https://example.invalid",
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return SyncChatClient(
        "test-key",
        "https://example.invalid",
        store,
        provider_models={"qwen-flash-sync": "qwen-flash"},
        max_concurrency=2,
        max_retries=max_retries,
        client=sdk,
    )


def test_batch_runs_immediately_and_reads_back_through_the_batch_codec() -> None:
    store = MemoryObjectStore()
    sent: list[dict] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        sent.append(body)
        assert request.url.path == "/chat/completions"
        prompt = body["messages"][0]["content"]
        if prompt == "reject":
            return httpx2.Response(400, json={"error": {"message": "bad request", "code": "invalid"}})
        return httpx2.Response(200, json=_completion(prompt.upper()))

    client = _client(handle, store)
    content = b"".join(_line(chapter, text) for chapter, text in ((1, "one"), (2, "reject"), (3, "three")))
    # Chunks need not align with lines.
    job_id = client.create_batch_job(content[offset : offset + 7] for offset in range(0, len(content), 7))

    assert job_id.startswith("translations/sync-batches/") and job_id.endswith(".jsonl")
    assert client.poll_batch_job(job_id) == BatchJobComplete(output_id=BatchOutputId(job_id))
    results = {
        result.key.chapter_id.int: result
        for line in b"".join(client.fetch_batch_output(BatchOutputId(job_id))).splitlines()
        for result in [CODEC.decode_result(line)]
    }
    assert {body["model"] for body in sent} == {"qwen-flash"} and {body["max_tokens"] for body in sent} == {64}
    assert isinstance(results[1], BatchItemSuccess) and results[1].text == "ONE"
    assert isinstance(results[3], BatchItemSuccess) and results[3].text == "THREE"
    assert isinstance(results[2], BatchItemFailure) and results[2].code == "400"


def test_rate_limited_requests_are_retried_by_the_sdk() -> None:
    store = MemoryObjectStore()
    calls = 0

    def handle(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx2.Response(429, headers={"retry-after-ms": "0"}, json={"error": {"message": "slow down"}})
        return httpx2.Response(200, json=_completion("ok"))

    client = _client(handle, store, max_retries=1)
    job_id = client.create_batch_job([_line(1, "hello")])

    (line,) = b"".join(client.fetch_batch_output(BatchOutputId(job_id))).splitlines()
    result = CODEC.decode_result(line)
    assert calls == 2 and isinstance(result, BatchItemSuccess) and result.text == "ok"
