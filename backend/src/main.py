"""
This is the main endpoint for the application.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth.router import router as auth_router
from .autolabels.router import router as autolabel_router
from .config import uvicorn_logger
from .filters.router import router as filters_router
from .labels.router import router as label_router
from .languages.router import router as language_router
from .novels.router import router as novel_router
from .redis import set_redis


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
