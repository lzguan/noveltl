from typing import Any

from arq.connections import RedisSettings

from .config import REDIS_HOST, REDIS_PORT
from .inference import Cluener
from .tasks import autolabel_infer, model_cache


async def startup(ctx: Any) -> None:
    model_cache["cluener"] = Cluener().model


class WorkerSettings:
    functions = [autolabel_infer]
    redis_settings = RedisSettings(host=REDIS_HOST, port=REDIS_PORT)

    on_startup = startup

    max_jobs = 2
    job_timeout = 600
