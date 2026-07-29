from src.autolabels.dispatch.celery import CeleryDispatcher
from src.autolabels.dispatch.dispatcher import AutoLabelDispatcher


def get_celery_dispatcher() -> AutoLabelDispatcher:
    return CeleryDispatcher()
