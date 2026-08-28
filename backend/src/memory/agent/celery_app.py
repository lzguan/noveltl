from celery import Celery

from src.config import redis_settings

# Job and task progress is persisted in Postgres, so no Celery result backend is needed.
app = Celery(
    "memory-agent",
    broker=f"redis://{redis_settings.REDIS_HOST}:{redis_settings.REDIS_PORT}/{redis_settings.AGENT_DATABASE}",
    include=["src.memory.agent.dispatch.celery"],
)
app.config_from_object("src.memory.agent.celeryconfig")
