from src.config import redis_settings
from src.jobs.broker import make_jobs_broker

broker = make_jobs_broker(
    f"redis://{redis_settings.REDIS_HOST}:{redis_settings.REDIS_PORT}/{redis_settings.AGENT_DATABASE}",
    queue_name="memory-agent",
)
