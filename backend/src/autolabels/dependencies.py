from src.autolabels.inference.dispatch.celery_dispatcher import CeleryDispatcher
from src.autolabels.inference.dispatch.dispatcher import AutoLabelDispatcher


def get_dispatcher() -> AutoLabelDispatcher:
    return CeleryDispatcher()
