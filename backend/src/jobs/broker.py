from taskiq_redis import RedisStreamBroker

from src.config import redis_settings


def make_jobs_broker(url: str, queue_name: str = "jobs") -> RedisStreamBroker:
    return RedisStreamBroker(
        url=url,
        queue_name=queue_name,
        consumer_group_name=queue_name,
        # A newly created consumer group reads the stream from its start, so tasks
        # enqueued before the first worker ever started are still delivered.
        consumer_id="0-0",
    )


broker = make_jobs_broker(
    f"redis://{redis_settings.REDIS_HOST}:{redis_settings.REDIS_PORT}/{redis_settings.JOBS_DATABASE}"
)
