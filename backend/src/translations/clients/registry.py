from collections.abc import Callable
from functools import lru_cache

from src.translations.clients.batch_jobs import BatchJobClient
from src.translations.clients.qwen_client import QwenClient
from src.translations.settings import qwen_settings
from src.translations.types import ModelName


@lru_cache
def _qwen_client_factory() -> BatchJobClient:

    return QwenClient(api_key=qwen_settings.QWEN_API_KEY, base_url=qwen_settings.QWEN_API_URL)


# Provider adapters populate this at startup; factories create clients per call.
BATCH_CLIENT_FACTORIES: dict[ModelName, Callable[[], BatchJobClient]] = {
    "qwen-plus": _qwen_client_factory,
    "qwen-flash": _qwen_client_factory,
}


def get_batch_client(model: ModelName) -> BatchJobClient:
    try:
        factory = BATCH_CLIENT_FACTORIES[model]
    except KeyError:
        raise ValueError(f"No batch client registered for model {model!r}") from None
    return factory()
