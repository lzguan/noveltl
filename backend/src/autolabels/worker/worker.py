import logging
from pathlib import Path
from typing import Any

from arq.connections import RedisSettings

from ...config import log_settings
from .config import REDIS_HOST, REDIS_PORT
from .inference import Cluener
from .tasks import autolabel_infer, model_cache

logger = logging.getLogger(__name__)


def configure_worker_logging() -> None:
    root_logger = logging.getLogger("src")
    level = getattr(logging, log_settings.LOG_LEVEL)
    root_logger.setLevel(level)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    if log_settings.LOG_OUTPUT in ["FILE", "BOTH"] and not any(
        isinstance(handler, logging.FileHandler) for handler in root_logger.handlers
    ):
        Path(log_settings.LOG_OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_settings.LOG_OUTPUT_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    if log_settings.LOG_OUTPUT in ["STREAM", "BOTH"] and not any(
        type(handler) is logging.StreamHandler for handler in root_logger.handlers
    ):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)


async def startup(ctx: Any) -> None:
    configure_worker_logging()
    logger.info("Autolabel worker starting")
    model_cache["cluener"] = Cluener().model
    logger.info("Autolabel worker model loaded model_name=cluener")


class WorkerSettings:
    functions = [autolabel_infer]
    redis_settings = RedisSettings(host=REDIS_HOST, port=REDIS_PORT)

    on_startup = startup

    max_jobs = 2
    job_timeout = 600
