import json
from collections import deque
from collections.abc import Iterable, Iterator, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any
from uuid import uuid4

from openai import APIConnectionError, APIStatusError, OpenAI

from src.files.storage import ObjectStore
from src.translations.clients.batch_jobs import (
    BatchJobClient,
    BatchJobComplete,
    BatchJobId,
    BatchJobPoll,
    BatchOutputId,
)
from src.translations.jsonl import iter_jsonl_lines


# Completes the whole batch inside create_batch_job, so a batch must finish within the
# submitting task's lease: keep batches small. Results go to the object store in the
# provider batch-output format; the object key is both the job ID and the output ID.
class SyncChatClient(BatchJobClient):
    def __init__(
        self,
        client: OpenAI,
        store: ObjectStore,
        *,
        provider_models: Mapping[str, str],
        max_concurrency: int = 4,
        max_retries: int = 5,
    ) -> None:
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        self.client = client.with_options(max_retries=max_retries)
        self.store = store
        self.provider_models = dict(provider_models)
        self.max_concurrency = max_concurrency

    def create_batch_job(self, content: Iterable[bytes]) -> BatchJobId:
        key = f"translations/sync-batches/{uuid4().hex}.jsonl"
        with (
            self.store.create(key, content_type="application/jsonl") as writer,
            ThreadPoolExecutor(max_workers=self.max_concurrency) as pool,
        ):
            pending: deque[Future[bytes]] = deque()
            # Read lazily and keep a bounded window in flight, writing results in request order.
            for line in iter_jsonl_lines(content):
                pending.append(pool.submit(self._complete, line))
                if len(pending) >= self.max_concurrency * 2:
                    writer.write(pending.popleft().result())
            while pending:
                writer.write(pending.popleft().result())
        return BatchJobId(key)

    def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        return BatchJobComplete(output_id=BatchOutputId(job_id))

    def fetch_batch_output(self, output_id: BatchOutputId) -> Iterator[bytes]:
        yield from self.store.fetch(output_id)

    def _complete(self, line: bytes) -> bytes:
        request = json.loads(line)
        custom_id = request["custom_id"]
        body: dict[str, Any] = dict(request["body"])
        body["model"] = self.provider_models.get(body["model"], body["model"])
        result: dict[str, object]
        try:
            completion = self.client.chat.completions.create(**body)
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
