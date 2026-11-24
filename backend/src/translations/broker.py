"""Publishing side of the translations queue; imports no action implementation."""

from taskiq import TaskiqScheduler
from taskiq_redis import ListRedisScheduleSource

from src.config import redis_settings
from src.jobs.broker import make_jobs_broker

_url = f"redis://{redis_settings.REDIS_HOST}:{redis_settings.REDIS_PORT}/{redis_settings.TRANSLATIONS_DATABASE}"

broker = make_jobs_broker(_url, queue_name="translations")
# Delayed polls wait here until the `taskiq scheduler` process sends them to the broker.
schedule_source = ListRedisScheduleSource(_url, prefix="translations-schedules")
scheduler = TaskiqScheduler(broker, sources=[schedule_source])
