from dataclasses import dataclass
from typing import Literal, Protocol

from src.translations.clients.batch_jobs import BatchJobClient


@dataclass(frozen=True)
class InferenceMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class InferenceRequest:
    """Text inference parameters translated into provider fields by the codec."""

    model: str
    messages: tuple[InferenceMessage, ...]
    temperature: float | None = None
    max_output_tokens: int | None = None


@dataclass(frozen=True)
class BatchItem[KeyT]:
    key: KeyT
    request: InferenceRequest


@dataclass(frozen=True)
class BatchItemSuccess[KeyT]:
    """A provider response; action-specific output validation is still required."""

    key: KeyT
    text: str
    finish_reason: str | None = None


@dataclass(frozen=True)
class BatchItemFailure[KeyT]:
    key: KeyT
    error: str
    code: str | None = None


type BatchItemResult[KeyT] = BatchItemSuccess[KeyT] | BatchItemFailure[KeyT]


class BatchLineCodec[KeyT](Protocol):
    """Map internal items to provider JSONL and recover their keys from results.

    Implementations own the reversible mapping between KeyT and custom_id.
    Decoding must not depend on request/output order or in-memory request state,
    since preparation and finalization can run in different worker processes.
    """

    def encode_request(self, item: BatchItem[KeyT]) -> bytes:
        """Encode one UTF-8 JSON object followed by a newline.

        Reject unsupported request parameters rather than silently dropping them.
        """
        ...

    def decode_result(self, line: bytes) -> BatchItemResult[KeyT]:
        """Decode one complete UTF-8 JSON line, with or without its line ending.

        Return BatchItemFailure for a reported per-item provider error. Raise
        ValueError for malformed records, including missing or invalid keys.
        Stream framing and task-level key validation belong to the caller.
        """
        ...


@dataclass(frozen=True)
class BatchBackend[KeyT]:
    """A provider factory supplies a client and its matching wire-format codec."""

    client: BatchJobClient
    codec: BatchLineCodec[KeyT]
