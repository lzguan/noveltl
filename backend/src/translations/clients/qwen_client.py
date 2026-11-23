from collections.abc import AsyncIterable, AsyncIterator
from tempfile import TemporaryFile

from openai import AsyncOpenAI

from src.translations.clients.batch_jobs import (
    BatchJobClient,
    BatchJobComplete,
    BatchJobFailed,
    BatchJobId,
    BatchJobPending,
    BatchJobPoll,
    BatchOutputId,
)


class QwenClient(BatchJobClient):
    """A client for Qwen batch jobs."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        async with self._client() as client:
            response = await client.batches.retrieve(job_id)
        if (
            response.status == "pending"
            or response.status == "in_progress"
            or response.status == "finalizing"
            or response.status == "validating"
        ):
            return BatchJobPending()
        elif response.status == "completed":
            if not response.output_file_id:
                raise ValueError(f"Batch job {job_id} completed without an output file ID")

            return BatchJobComplete(output_id=BatchOutputId(response.output_file_id))
        else:
            return BatchJobFailed(error=f"Batch job {job_id} failed with status {response.status}: response={response}")

    async def create_batch_job(self, content: AsyncIterable[bytes]) -> BatchJobId:
        # The SDK uploads a file object, not an async stream, so spool the input first.
        with TemporaryFile(mode="w+b") as spool:
            async for chunk in content:
                spool.write(chunk)
            spool.seek(0)
            async with self._client() as client:
                file_obj = await client.with_options(max_retries=0).files.create(
                    file=("input.jsonl", spool), purpose="batch"
                )
                response = await client.batches.create(
                    input_file_id=file_obj.id, endpoint="/v1/chat/completions", completion_window="24h"
                )
        return BatchJobId(response.id)

    async def fetch_batch_output(self, output_id: BatchOutputId) -> AsyncIterator[bytes]:
        async with self._client() as client:
            async with client.files.with_streaming_response.content(file_id=output_id) as response:
                async for chunk in response.iter_bytes():
                    yield chunk
