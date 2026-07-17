"""
This is the main endpoint for the application.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth.router import router as auth_router
from .autolabels.router import router as autolabel_router
from .config import log_settings, uvicorn_logger
from .editing.router import router as editing_router
from .filters.router import router as filters_router
from .labels.router import router as label_router
from .languages.router import router as language_router
from .novels.router import router as novel_router
from .redis_conn import set_redis
from .requests.router import router as requests_router

logger = logging.getLogger("src")
if log_settings.LOG_LEVEL == "DEBUG":
    logger.setLevel(logging.DEBUG)
elif log_settings.LOG_LEVEL == "INFO":
    logger.setLevel(logging.INFO)
elif log_settings.LOG_LEVEL == "WARNING":
    logger.setLevel(logging.WARNING)
elif log_settings.LOG_LEVEL == "ERROR":
    logger.setLevel(logging.ERROR)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

if log_settings.LOG_OUTPUT in ["FILE", "BOTH"]:
    fh = logging.FileHandler(log_settings.LOG_OUTPUT_FILE)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

if log_settings.LOG_OUTPUT in ["STREAM", "BOTH"]:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)


@asynccontextmanager
async def lifespan(app: FastAPI):
    uvicorn_logger.info("Server starting.")
    async with set_redis():
        uvicorn_logger.info("Redis connection created.")
        yield
        uvicorn_logger.info("Redis connection aborting.")
    uvicorn_logger.info("Closing server.")


app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)
app.include_router(novel_router)
app.include_router(label_router)
app.include_router(autolabel_router)
app.include_router(language_router)
app.include_router(filters_router)
app.include_router(editing_router)
app.include_router(requests_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
