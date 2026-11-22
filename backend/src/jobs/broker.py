from taskiq_redis import RedisStreamBroker

from src.config import redis_settings

# Broker for the generic jobs worker: short, database-bound background jobs. Keep this
# package free of heavy dependencies so task modules can import it cheaply.
# Run the worker with: taskiq worker src.jobs.broker:broker <task modules...>
#
# A stream broker acknowledges a message only after its task finishes; unacknowledged
# messages are redelivered after `idle_timeout`, so tasks must be idempotent.
broker = RedisStreamBroker(
    url=f"redis://{redis_settings.REDIS_HOST}:{redis_settings.REDIS_PORT}/{redis_settings.JOBS_DATABASE}",
    queue_name="jobs",
    consumer_group_name="jobs",
)
