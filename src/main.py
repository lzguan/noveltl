"""
This is the main endpoint for the application.
"""
import logging

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from .auth.router import router as auth_router
from .novels.router import router as novel_router
from .labels.router import router as label_router

app = FastAPI()
app.include_router(auth_router)
app.include_router(novel_router)
app.include_router(label_router)