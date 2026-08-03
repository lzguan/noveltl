from celery import Celery

from src.config import redis_settings

# no backend needed since we don't need to store results
app = Celery(
    "tasks",
    broker=f"redis://{redis_settings.REDIS_HOST}:{redis_settings.REDIS_PORT}/{redis_settings.FILTERS_DATABASE}",
    include=["src.filters.dispatch.celery"],
)
app.config_from_object("src.filters.celeryconfig")
