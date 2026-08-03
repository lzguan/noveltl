from src.filters.dispatch.celery import CeleryRunnerDispatcher
from src.filters.dispatch.dispatcher import RunnerDispatcher


def get_dispatcher() -> RunnerDispatcher:
    return CeleryRunnerDispatcher()
