"""OpenAI-compatible Chat Completions batch JSONL, without transport or SDK state."""

import json
from typing import Literal

from pydantic import ConfigDict, Field, TypeAdapter

from src.schemas import Model
from src.translations.batch_lines import BatchItem, BatchItemFailure, BatchItemResult, BatchItemSuccess


class _WireModel(Model):
    model_config = ConfigDict(alias_generator=None, strict=True)


class _Error(_WireModel):
    message: str
    code: str | None = None


class _Message(_WireModel):
    role: Literal["assistant"]
    content: str | None = None
    refusal: str | None = None


class _Choice(_WireModel):
    index: int
    message: _Message
    finish_reason: str


class _Body(_WireModel):
    choices: list[_Choice] | None = None
    error: _Error | None = None


class _Response(_WireModel):
    status_code: int
    body: _Body


class _ResultLine(_WireModel):
    custom_id: str = Field(min_length=1)
    response: _Response | None = None
    error: _Error | None = None


class OpenAIChatBatchCodec[KeyT]:
    """Encode text requests and decode single-choice chat batch results.

    Keys are JSON-serialized inside custom_id, so another worker can recover
    them with the same TypeAdapter without request history. Provider-specific
    ID limits and model capabilities remain the backend's responsibility.

    max_completion_tokens is the OpenAI default; compatible backends may select
    max_tokens explicitly. This codec does not implement the Responses API.
    """

    def __init__(
        self,
        key_adapter: TypeAdapter[KeyT],
        *,
        max_tokens_field: Literal["max_completion_tokens", "max_tokens"] = "max_completion_tokens",
    ) -> None:
        self._key_adapter = key_adapter
        self._max_tokens_field = max_tokens_field

    def encode_request(self, item: BatchItem[KeyT]) -> bytes:
        request = item.request
        body: dict[str, object] = {
            "model": request.model,
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            body[self._max_tokens_field] = request.max_output_tokens
        line = {
            "custom_id": self._key_adapter.dump_json(item.key, by_alias=False, warnings="error").decode("utf-8"),
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": body,
        }
        return json.dumps(line, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8") + b"\n"

    def decode_result(self, line: bytes) -> BatchItemResult[KeyT]:
        result = _ResultLine.model_validate_json(line)
        key = self._key_adapter.validate_json(result.custom_id)
        if result.error is not None:
            return BatchItemFailure(key=key, error=result.error.message, code=result.error.code)
        response = result.response
        if response is None:
            raise ValueError("Batch result has neither a response nor an error")
        if response.body.error is not None:
            error = response.body.error
            return BatchItemFailure(key=key, error=error.message, code=error.code)
        if not 200 <= response.status_code < 300:
            return BatchItemFailure(
                key=key, error=f"Batch request returned HTTP {response.status_code}", code=str(response.status_code)
            )
        choices = response.body.choices
        if choices is None or len(choices) != 1 or choices[0].index != 0:
            raise ValueError("Expected exactly one chat completion choice with index 0")
        choice = choices[0]
        if choice.message.refusal is not None:
            return BatchItemFailure(key=key, error=choice.message.refusal, code="refusal")
        if choice.finish_reason != "stop":
            return BatchItemFailure(
                key=key,
                error=f"Chat completion did not finish normally: {choice.finish_reason}",
                code=choice.finish_reason,
            )
        if choice.message.content is None:
            raise ValueError("Chat completion has no text content")
        return BatchItemSuccess(key=key, text=choice.message.content, finish_reason=choice.finish_reason)
