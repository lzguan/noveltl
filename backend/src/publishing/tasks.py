import uuid

from src.database import AsyncSessionLocal
from src.jobs.broker import broker
from src.models import Base  # noqa: F401
from src.publishing.dispatch import PUBLISH_NOVEL
from src.publishing.processing import process_publish_job


@broker.task(task_name=PUBLISH_NOVEL)
async def publish_novel(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await process_publish_job(db, uuid.UUID(job_id))
