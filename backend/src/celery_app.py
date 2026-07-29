from celery import Celery

from src.config import redis_settings

# no backend needed since we don't need to store results
app = Celery(
    "tasks",
    broker=f"redis://{redis_settings.REDIS_HOST}:{redis_settings.REDIS_PORT}/0",
    include=["src.autolabels.dispatch.celery"],
)
