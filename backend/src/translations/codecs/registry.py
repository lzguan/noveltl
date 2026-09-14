from collections.abc import Callable

from pydantic import TypeAdapter

from src.translations.batch_lines import BatchLineCodec
from src.translations.codecs.openai_chat import OpenAIChatBatchCodec
from src.translations.types import ModelName, TranslationDataKey

type CodecFactory = Callable[[], BatchLineCodec[TranslationDataKey]]

MODEL_CODECS: dict[ModelName, CodecFactory] = {
    "qwen-plus": lambda: OpenAIChatBatchCodec(TypeAdapter(TranslationDataKey), max_tokens_field="max_tokens"),
    "qwen-flash": lambda: OpenAIChatBatchCodec(TypeAdapter(TranslationDataKey), max_tokens_field="max_tokens"),
}


def get_codec(model: ModelName) -> BatchLineCodec[TranslationDataKey]:
    """Construct the codec for a supported model."""
    return MODEL_CODECS[model]()
