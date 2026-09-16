from src.autolabels.dispatch.celery_dispatcher import CeleryDispatcher
from src.autolabels.dispatch.dispatcher import AutoLabelDispatcher


def get_dispatcher() -> AutoLabelDispatcher:
    return CeleryDispatcher()
