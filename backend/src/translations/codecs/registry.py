import json
import re
from collections.abc import Callable
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer, TypeAdapter

from src.translations.codecs.batch_lines import BatchLineCodec
from src.translations.codecs.openai_chat import OpenAIChatBatchCodec
from src.translations.types import ModelName, TranslationDataKey

type CodecFactory = Callable[[], BatchLineCodec[TranslationDataKey]]


def _expand_compact_key(value: object) -> object:
    if isinstance(value, str):
        match = re.fullmatch(r"([0-9a-f]{32})_(chapter|memories)", value)
        if match is not None:
            return {"chapter_id": match[1], "data_name": match[2]}
        if value.startswith(("{", "[")):
            value = json.loads(value)
    if isinstance(value, list) and len(value) == 2:
        return {"chapter_id": value[0], "data_name": value[1]}
    # Continue accepting results from artifacts prepared with the older codec.
    return value


type _CompactKey = Annotated[
    TranslationDataKey,
    BeforeValidator(_expand_compact_key),
    PlainSerializer(lambda key: f"{key.chapter_id.hex}_{key.data_name}", return_type=str),
]


MODEL_CODECS: dict[ModelName, CodecFactory] = {
    "qwen-plus": lambda: OpenAIChatBatchCodec(TypeAdapter(TranslationDataKey), max_tokens_field="max_tokens"),
    "qwen-flash": lambda: OpenAIChatBatchCodec(TypeAdapter(TranslationDataKey), max_tokens_field="max_tokens"),
    "deepseek/deepseek-v4.1-flash": lambda: OpenAIChatBatchCodec(
        TypeAdapter(_CompactKey), max_tokens_field="max_tokens", custom_id_format="string"
    ),
}


def get_codec(model: ModelName) -> BatchLineCodec[TranslationDataKey]:
    """Construct the codec for a supported model."""
    return MODEL_CODECS[model]()
