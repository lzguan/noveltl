import json
from collections.abc import AsyncIterable, AsyncIterator, Callable, Mapping
from typing import Any
from uuid import uuid4

from openai import APIConnectionError, APIStatusError, AsyncOpenAI

from src.files.async_storage import AsyncObjectStore
from src.lib.async_buffer import async_buffer
from src.translations.clients.batch_jobs import (
    BatchJobClient,
    BatchJobComplete,
    BatchJobId,
    BatchJobPoll,
    BatchOutputId,
)
from src.translations.jsonl import aiter_jsonl_lines


# Completes the whole batch inside create_batch_job, so a batch must finish within the
# submitting task's lease: keep batches small. Results go to the object store in the
# provider batch-output format; the object key is both the job ID and the output ID.
class SyncChatClient(BatchJobClient):
    def __init__(
        self,
        client_factory: Callable[[], AsyncOpenAI],
        store: AsyncObjectStore,
        *,
        provider_models: Mapping[str, str],
        max_concurrency: int = 4,
        max_retries: int = 5,
    ) -> None:
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        # A factory, not a client: a Celery step runs on a fresh event loop each time, and
        # an async client binds to the loop it first runs on.
        self.client_factory = client_factory
        self.store = store
        self.provider_models = dict(provider_models)
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries

    async def create_batch_job(self, content: AsyncIterable[bytes]) -> BatchJobId:
        key = f"translations/sync-batches/{uuid4().hex}.jsonl"
        async with self.client_factory().with_options(max_retries=self.max_retries) as client:
            requests = (self._complete(client, line) async for line in aiter_jsonl_lines(content))
            async with self.store.create(key, content_type="application/jsonl") as writer:
                async for result in async_buffer(requests, size=self.max_concurrency):
                    await writer.write(result)
        return BatchJobId(key)

    async def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        return BatchJobComplete(output_id=BatchOutputId(job_id))

    async def fetch_batch_output(self, output_id: BatchOutputId) -> AsyncIterator[bytes]:
        async for chunk in self.store.fetch(output_id):
            yield chunk

    async def _complete(self, client: AsyncOpenAI, line: bytes) -> bytes:
        request = json.loads(line)
        custom_id = request["custom_id"]
        body: dict[str, Any] = dict(request["body"])
        body["model"] = self.provider_models.get(body["model"], body["model"])
        result: dict[str, object]
        try:
            completion = await client.chat.completions.create(**body)
            result = {
                "custom_id": custom_id,
                "response": {"status_code": 200, "body": completion.model_dump(mode="json")},
            }
        except APIStatusError as error:
            result = {
                "custom_id": custom_id,
                "response": {
                    "status_code": error.status_code,
                    "body": {"error": {"message": error.message, "code": str(error.status_code)}},
                },
            }
        except APIConnectionError as error:
            result = {"custom_id": custom_id, "error": {"message": str(error), "code": "request_failed"}}
        return json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"
