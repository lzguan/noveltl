"""
This is the main endpoint for the application.
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
from .redis import set_redis
from .config import uvicorn_logger

@asynccontextmanager
async def lifespan(app : FastAPI):
    uvicorn_logger.info("Server starting.")
    async with set_redis():
        uvicorn_logger.info("Redis connection created.")
        yield
        uvicorn_logger.info("Redis connection aborting.")
    uvicorn_logger.info("Closing server.")

from .auth.router import router as auth_router
from .novels.router import router as novel_router
from .labels.router import router as label_router
from .autolabels.router import router as autolabel_router

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
app.include_router(novel_router)
app.include_router(label_router)
app.include_router(autolabel_router)