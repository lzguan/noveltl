from celery import Celery

from src.config import redis_settings

app = Celery(
    "translations",
    broker=f"redis://{redis_settings.REDIS_HOST}:{redis_settings.REDIS_PORT}/{redis_settings.TRANSLATIONS_DATABASE}",
    include=["src.translations.actions"],
)
app.config_from_object("src.translations.celeryconfig")
