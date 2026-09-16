from collections.abc import Iterable, Iterator

from openai import OpenAI

from src.streaming import buffered_reader
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
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def poll_batch_job(self, job_id: BatchJobId) -> BatchJobPoll:
        response = self.client.batches.retrieve(job_id)
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

    def create_batch_job(self, content: Iterable[bytes]) -> BatchJobId:
        # This stream cannot rewind. Task recovery must reopen it after failure.
        with buffered_reader(content) as stream:
            file_obj = self.client.with_options(max_retries=0).files.create(
                file=("input.jsonl", stream), purpose="batch"
            )
        response = self.client.batches.create(
            input_file_id=file_obj.id, endpoint="/v1/chat/completions", completion_window="24h"
        )
        return BatchJobId(response.id)

    def fetch_batch_output(self, output_id: BatchOutputId) -> Iterator[bytes]:
        with self.client.files.with_streaming_response.content(file_id=output_id) as response:
            yield from response.iter_bytes()
