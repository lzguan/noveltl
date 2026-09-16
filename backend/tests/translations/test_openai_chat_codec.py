import json
from uuid import UUID

import pytest
from pydantic import TypeAdapter

from src.translations.codecs.batch_lines import (
    BatchItem,
    BatchItemFailure,
    BatchItemSuccess,
    BatchLineCodec,
    InferenceMessage,
    InferenceRequest,
)
from src.translations.codecs.openai_chat import OpenAIChatBatchCodec
from src.translations.types import TranslationDataKey


def test_request_mapping_and_key_recovery_in_fresh_codec() -> None:
    key = TranslationDataKey(UUID(int=1), "chapter")
    codec: BatchLineCodec[TranslationDataKey] = OpenAIChatBatchCodec(TypeAdapter(TranslationDataKey))
    request = BatchItem(
        key=key,
        request=InferenceRequest(
            model="example-model",
            messages=(InferenceMessage(role="user", content='第一章\n"Hello"'),),
            temperature=0.0,
            max_output_tokens=100,
        ),
    )
    line = codec.encode_request(request)
    assert line.endswith(b"\n") and line.count(b"\n") == 1
    encoded = json.loads(line)
    assert encoded["method"] == "POST" and encoded["url"] == "/v1/chat/completions"
    assert encoded["body"] == {
        "model": "example-model",
        "messages": [{"role": "user", "content": '第一章\n"Hello"'}],
        "temperature": 0.0,
        "max_completion_tokens": 100,
    }
    output = json.dumps(
        {
            "custom_id": encoded["custom_id"],
            "error": None,
            "response": {
                "status_code": 200,
                "request_id": "provider-request",
                "body": {
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "Translation"},
                        }
                    ],
                    "usage": {"total_tokens": 123},
                },
            },
        }
    ).encode()
    fresh = OpenAIChatBatchCodec(TypeAdapter(TranslationDataKey))
    assert fresh.decode_result(output) == BatchItemSuccess(key=key, text="Translation", finish_reason="stop")


def test_compatible_token_field_and_omitted_options() -> None:
    codec = OpenAIChatBatchCodec(TypeAdapter(str), max_tokens_field="max_tokens")
    messages = (InferenceMessage(role="user", content="text"),)
    body = json.loads(codec.encode_request(BatchItem(key="a", request=InferenceRequest(model="m", messages=messages))))[
        "body"
    ]
    assert "temperature" not in body and "max_tokens" not in body and "max_completion_tokens" not in body
    body = json.loads(
        codec.encode_request(
            BatchItem(key="a", request=InferenceRequest(model="m", messages=messages, max_output_tokens=12))
        )
    )["body"]
    assert body["max_tokens"] == 12 and "max_completion_tokens" not in body


@pytest.mark.parametrize("location", ["batch", "response"])
def test_provider_errors_preserve_key_and_details(location: str) -> None:
    error = {"code": "batch_expired", "message": "Not processed"}
    line = (
        {"custom_id": '"request-a"', "response": None, "error": error}
        if location == "batch"
        else {
            "custom_id": '"request-a"',
            "response": {"status_code": 400, "body": {"error": error}},
            "error": None,
        }
    )
    result = OpenAIChatBatchCodec(TypeAdapter(str)).decode_result(json.dumps(line).encode())
    assert result == BatchItemFailure(key="request-a", error="Not processed", code="batch_expired")


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls"])
def test_unfinished_text_is_not_success(reason: str) -> None:
    line = {
        "custom_id": '"a"',
        "response": {
            "status_code": 200,
            "body": {
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": reason,
                        "message": {"role": "assistant", "content": "Partial"},
                    }
                ]
            },
        },
    }
    result = OpenAIChatBatchCodec(TypeAdapter(str)).decode_result(json.dumps(line).encode())
    assert isinstance(result, BatchItemFailure) and result.key == "a" and result.code == reason


@pytest.mark.parametrize(
    "line",
    [
        b"not json",
        b'{"custom_id":"not json"}',
        b'{"response":null}',
        b'{"custom_id":"1"}',
        b'{"custom_id":"\\"a\\"","response":{"status_code":200,"body":{"choices":[]}}}',
    ],
)
def test_malformed_results_raise(line: bytes) -> None:
    with pytest.raises(ValueError):
        OpenAIChatBatchCodec(TypeAdapter(str)).decode_result(line)
