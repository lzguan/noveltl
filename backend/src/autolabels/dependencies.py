from src.autolabels.inference.dispatch.celery_dispatcher import CeleryDispatcher
from src.autolabels.inference.dispatch.dispatcher import AutoLabelDispatcher
from src.autolabels.promotions.dispatch.dispatcher import PromotionDispatcher
from src.autolabels.promotions.dispatch.taskiq_dispatcher import TaskiqPromotionDispatcher


def get_dispatcher() -> AutoLabelDispatcher:
    return CeleryDispatcher()


def get_promotion_dispatcher() -> PromotionDispatcher:
    return TaskiqPromotionDispatcher()
