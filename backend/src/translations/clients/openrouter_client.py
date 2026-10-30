"""OpenRouter's inline batch API behind the worker's JSONL transport contract."""

import json
from collections.abc import Iterable, Iterator
from itertools import chain
from typing import Literal
from urllib.parse import quote

import httpx2
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from src.translations.clients.batch_jobs import (
    BatchJobClient,
    BatchJobComplete,
    BatchJobFailed,
    BatchJobId,
    BatchJobPending,
    BatchJobPoll,
    BatchOutputId,
)
from src.translations.jsonl import iter_jsonl_lines


class _ChatBody(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    model: str = Field(min_length=1)


class _RequestLine(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    custom_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    method: Literal["POST"]
    url: Literal["/v1/chat/completions"]
    body: _ChatBody


class _Error(BaseModel):
    message: str


class _Batch(BaseModel):
    id: str = Field(min_length=1)
    status: Literal[
        "validating", "in_progress", "finalizing", "cancelling", "completed", "failed", "expired", "cancelled"
    ]
    results: list[dict[str, JsonValue]] | None = None
    error: _Error | None = None


def _raise_for_status(response: httpx2.Response) -> None:
    try:
        response.raise_for_status()
    except httpx2.HTTPStatusError as error:
        # Celery persists str(error); keep the provider's validation detail
        # available there without dumping the submitted chapter payload.
        detail = response.text[:4096]
        raise httpx2.HTTPStatusError(
            f"{error}\nOpenRouter response: {detail}", request=error.request, response=response
        ) from error


def _encode_batch(content: Iterable[bytes]) -> Iterator[bytes]:
    lines = iter_jsonl_lines(content)
    first_line = next(lines, None)
    if first_line is None:
        raise ValueError("Cannot submit an empty OpenRouter batch")
    first = _RequestLine.model_validate_json(first_line)
    # OpenRouter requires metadata before requests. Stream the array so a large
    # prepared artifact need not be buffered or replayed by the HTTP client.
    metadata = {"endpoint": first.url, "model": first.body.model, "completion_window": "24h"}
    yield json.dumps(metadata).encode("utf-8")[:-1] + b',"requests":['
    seen: set[str] = set()
    for item in chain((first,), (_RequestLine.model_validate_json(line) for line in lines)):
        if item.body.model != first.body.model:
            raise ValueError("OpenRouter batches must use a single model")
        if item.custom_id in seen:
            raise ValueError("OpenRouter batch custom_id values must be unique")
        if seen:
            yield b","
        seen.add(item.custom_id)
        yield json.dumps(
            {"custom_id": item.custom_id, "body": item.body.model_dump(mode="json")},
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    yield b"]}"


class OpenRouterClient(BatchJobClient):
    def __init__(self, api_key: str, base_url: str) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY must be configured")
        self.client = httpx2.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=60,
        )

    def create_batch_job(self, content: Iterable[bytes]) -> BatchJobId:
        # HTTPX does not automatically retry this single-use submission stream.
        response = self.client.post("batches", content=_encode_batch(content))
        _raise_for_status(response)
        batch = _Batch.model_validate_json(response.content)
        return BatchJobId(batch.id)

    def _retrieve(self, batch_id: str) -> _Batch:
        response = self.client.get(f"batches/{quote(batch_id, safe='')}")
        _raise_for_status(response)
        batch = _Batch.model_validate_json(response.content)
        if batch.id != batch_id:
            raise ValueError("OpenRouter returned a different batch ID")
        return batch

    def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        batch = self._retrieve(job_id)
        if batch.status == "completed":
            if batch.results is None:
                return BatchJobPending()
            # Results have no file ID. The batch ID is a durable output handle
            # that another worker can retrieve without this client's state.
            return BatchJobComplete(output_id=BatchOutputId(batch.id))
        if batch.status in {"failed", "expired", "cancelled"}:
            detail = f": {batch.error.message}" if batch.error is not None else ""
            return BatchJobFailed(error=f"OpenRouter batch {batch.id} {batch.status}{detail}")
        return BatchJobPending()

    def fetch_batch_output(self, output_id: BatchOutputId) -> Iterator[bytes]:
        batch = self._retrieve(output_id)
        if batch.status != "completed" or batch.results is None:
            raise ValueError("OpenRouter batch results are not available")
        for result in batch.results:
            yield json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
