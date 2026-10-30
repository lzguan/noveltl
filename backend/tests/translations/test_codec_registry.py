import json
from typing import get_args
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.translations.clients.registry import BATCH_CLIENT_FACTORIES
from src.translations.codecs.batch_lines import BatchItem, BatchItemSuccess, InferenceMessage, InferenceRequest
from src.translations.codecs.registry import MODEL_CODECS, get_codec
from src.translations.schemas import TranslateConfig
from src.translations.types import ModelName, TranslationDataKey


def test_supported_models_have_compatible_codecs() -> None:
    assert set(MODEL_CODECS) == set(get_args(ModelName.__value__))
    assert set(BATCH_CLIENT_FACTORIES) == set(MODEL_CODECS)
    for model in MODEL_CODECS:
        assert TranslateConfig(model=model).model == model
        codec = get_codec(model)
        assert get_codec(model) is not codec
        item = BatchItem(
            key=TranslationDataKey(UUID(int=1), "chapter"),
            request=InferenceRequest(
                model=model,
                messages=(InferenceMessage(role="user", content="text"),),
                max_output_tokens=10,
            ),
        )
        body = json.loads(codec.encode_request(item))["body"]
        assert body["model"] == model and body["max_tokens"] == 10
        assert "max_completion_tokens" not in body


def test_unknown_model_is_rejected_by_config() -> None:
    with pytest.raises(ValidationError):
        TranslateConfig.model_validate({"model": "unknown-model"})


@pytest.mark.parametrize("legacy_format", ["object", "array"])
def test_openrouter_decodes_keys_from_previously_prepared_artifacts(legacy_format: str) -> None:
    key = TranslationDataKey(UUID(int=1), "memories")
    result = {
        "custom_id": json.dumps(
            {"chapter_id": str(key.chapter_id), "data_name": key.data_name}
            if legacy_format == "object"
            else [str(key.chapter_id), key.data_name]
        ),
        "response": {
            "status_code": 200,
            "body": {
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "[]"}, "finish_reason": "stop"}]
            },
        },
    }
    assert get_codec("deepseek/deepseek-v4.1-flash").decode_result(json.dumps(result).encode()) == BatchItemSuccess(
        key=key, text="[]", finish_reason="stop"
    )
