"""
This is the main endpoint for the application.
"""

import logging

from fastapi import FastAPI

from src.auth.router import router as auth_router
from src.autolabels.router import router as autolabel_router
from src.config import log_settings
from src.editing.router import router as editing_router
from src.filters.router import router as filter_router
from src.labels.router import router as label_router
from src.languages.router import router as language_router
from src.memory.plugins.glossary.router import router as glossary_memory_router
from src.memory.router import router as memory_router
from src.novels.router import router as novel_router
from src.requests.router import router as requests_router

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


app = FastAPI()

app.include_router(auth_router)
app.include_router(novel_router)
app.include_router(label_router)
app.include_router(autolabel_router)
app.include_router(language_router)
app.include_router(editing_router)
app.include_router(requests_router)
app.include_router(filter_router)
app.include_router(memory_router)
app.include_router(glossary_memory_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
