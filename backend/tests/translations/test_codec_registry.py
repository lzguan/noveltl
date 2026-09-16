import json
from typing import get_args
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.translations.codecs.batch_lines import BatchItem, InferenceMessage, InferenceRequest
from src.translations.codecs.registry import MODEL_CODECS, get_codec
from src.translations.schemas import TranslateConfig
from src.translations.types import ModelName, TranslationDataKey


def test_supported_models_have_compatible_codecs() -> None:
    assert set(MODEL_CODECS) == set(get_args(ModelName.__value__))
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
