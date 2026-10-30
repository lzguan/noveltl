from collections.abc import Callable
from functools import lru_cache

from src.translations.clients.batch_jobs import BatchJobClient
from src.translations.types import ModelName


@lru_cache
def _qwen_client_factory() -> BatchJobClient:
    # API processes import the registry to dispatch tasks, but only workers
    # resolving a client need the provider SDK and credentials.
    from src.config import qwen_settings
    from src.translations.clients.qwen_client import QwenClient

    return QwenClient(api_key=qwen_settings.QWEN_API_KEY, base_url=qwen_settings.QWEN_API_URL)


@lru_cache
def _openrouter_client_factory() -> BatchJobClient:
    from src.config import openrouter_settings
    from src.translations.clients.openrouter_client import OpenRouterClient

    return OpenRouterClient(
        api_key=openrouter_settings.OPENROUTER_API_KEY, base_url=openrouter_settings.OPENROUTER_API_URL
    )


# Factories resolve provider dependencies on first use in each process.
BATCH_CLIENT_FACTORIES: dict[ModelName, Callable[[], BatchJobClient]] = {
    "qwen-plus": _qwen_client_factory,
    "qwen-flash": _qwen_client_factory,
    "deepseek/deepseek-v4.1-flash": _openrouter_client_factory,
}


def get_batch_client(model: ModelName) -> BatchJobClient:
    try:
        factory = BATCH_CLIENT_FACTORIES[model]
    except KeyError:
        raise ValueError(f"No batch client registered for model {model!r}") from None
    return factory()
