from src.filters.dispatch.celery_dispatcher import CeleryRunnerDispatcher
from src.filters.dispatch.dispatcher import RunnerDispatcher


def get_dispatcher() -> RunnerDispatcher:
    return CeleryRunnerDispatcher()
