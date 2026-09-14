from collections.abc import Callable

from src.translations.batch_jobs import BatchJobClient
from src.translations.types import ModelName

# Provider adapters populate this at startup; factories create clients per call.
BATCH_CLIENT_FACTORIES: dict[ModelName, Callable[[], BatchJobClient]] = {}


def get_batch_client(model: ModelName) -> BatchJobClient:
    try:
        factory = BATCH_CLIENT_FACTORIES[model]
    except KeyError:
        raise ValueError(f"No batch client registered for model {model!r}") from None
    return factory()
