from .tasks import model_cache, autolabel_infer
from .inference import Cluener
from arq.connections import RedisSettings
from .config import REDIS_PORT, REDIS_HOST

async def startup(ctx):
    model_cache['cluener'] = Cluener().model

class WorkerSettings:
    functions = [autolabel_infer]
    redis_settings = RedisSettings(host=REDIS_HOST, port=REDIS_PORT)

    on_startup = startup

    max_jobs = 2
    job_timeout = 600