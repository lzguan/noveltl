import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
from collections import defaultdict
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO
from uuid import UUID

import boto3
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.files.dependencies import _store_options, get_object_store
from src.files.models import StoredFile
from src.files.storage import ObjectStore
from src.models import Base  # noqa: F401  registers every mapper
from src.novels.models import Chapter
from src.translations.jsonl import iter_jsonl_lines
from src.translations.models import TranslationJob, TranslationStage, TranslationTask
from src.translations.schemas import stage_config
from src.translations.types import TranslationTaskStatus

KIND = "translation_job.v1"
REPO = Path(__file__).resolve().parents[2]
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
NAME_FORMAT = "%Y%m%dT%H%M%S%fZ"
SUFFIX = ".jsonl.gz"


def _git_version() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        dirty = subprocess.run(
            ["git", "-C", str(REPO), "status", "--porcelain", "--", "backend/src", "backend/scripts"],
            capture_output=True,
            text=True,
            check=True,
        )
    except OSError, subprocess.CalledProcessError:
        return "unknown"
    return sha.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")


def _read_records(object_store: ObjectStore, object_key: str) -> Iterator[dict[str, Any]]:
    raw = b"".join(object_store.fetch(object_key))
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    for line in iter_jsonl_lines([raw]):
        if line.strip():
            yield json.loads(line)


def _condition(job: TranslationJob, stages: list[TranslationStage]) -> dict[str, Any]:
    return {
        "v": 1,
        "stages": [
            {"action": s.action, "config": stage_config(s.action, s.config).model_dump(mode="json")} for s in stages
        ],
        "batch_size": job.config.get("batch_size"),
        "slice": None,
        "pipeline": None,
    }


def _blob_content(payload: Any) -> tuple[str, str]:
    """Text payloads as-is, anything else as canonical JSON."""
    if isinstance(payload, str):
        return "text", payload
    return "json", json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def finished_job_ids(session: Session, since: datetime, until: datetime) -> list[UUID]:
    unfinished = func.count().filter(
        (TranslationTask.status != TranslationTaskStatus.COMPLETE) | TranslationTask.output_file_id.is_(None)
    )
    last_update = func.max(TranslationTask.updated_at)
    return list(
        session.scalars(
            select(TranslationStage.job_id)
            .join(TranslationTask, TranslationTask.stage_id == TranslationStage.stage_id)
            .group_by(TranslationStage.job_id)
            .having(unfinished == 0, last_update > since, last_update <= until)
            .order_by(TranslationStage.job_id)
        )
    )


def dump_translation_jobs(
    session: Session, object_store: ObjectStore, job_ids: list[UUID], *, since: datetime, until: datetime
) -> Iterator[dict[str, Any]]:
    """
    Dump translation jobs from the database as the JSONL records of one export run.

    Args:
        session: SQLAlchemy session.
        object_store: Store holding the task output files.
        job_ids: Finished jobs to export.
        since: Watermark the run starts after (exclusive).
        until: Watermark the run ends at (inclusive).
    Returns:
        A `header` record, then per job a `job` record followed by its `chapter`, `blob` and `stream` records.
        Each distinct payload is emitted once per run as a `blob` (kind, content and their combined hash), before
        the first `stream` that references it.
    """
    yield {
        "type": "header",
        "kind": KIND,
        "producer": {
            "name": "export_db",
            "version": _git_version(),
            "source": {"database": session.get_bind().engine.url.database},
            "exported_at": datetime.now(UTC).isoformat(),
        },
        "watermark": {"since": since.isoformat(), "until": until.isoformat()},
        "job_ids": [str(job_id) for job_id in job_ids],
    }
    if not job_ids:
        return

    jobs = {
        job.job_id: job for job in session.scalars(select(TranslationJob).where(TranslationJob.job_id.in_(job_ids)))
    }
    stages_by_job: dict[UUID, list[TranslationStage]] = defaultdict(list)
    for stage in session.scalars(
        select(TranslationStage)
        .where(TranslationStage.job_id.in_(job_ids))
        .order_by(TranslationStage.job_id, TranslationStage.stage_num)
    ):
        stages_by_job[stage.job_id].append(stage)
    stage_ids = [stage.stage_id for stages in stages_by_job.values() for stage in stages]
    tasks_by_stage: dict[UUID, list[TranslationTask]] = defaultdict(list)
    for task in session.scalars(
        select(TranslationTask).where(TranslationTask.stage_id.in_(stage_ids)).order_by(TranslationTask.task_id)
    ):
        tasks_by_stage[task.stage_id].append(task)
    output_ids = [task.output_file_id for tasks in tasks_by_stage.values() for task in tasks if task.output_file_id]
    object_keys = dict(
        session.execute(
            select(StoredFile.file_id, StoredFile.object_key).where(StoredFile.file_id.in_(output_ids))
        ).all()
    )
    chapters_by_id = {
        chapter_id: (num, title)
        for chapter_id, num, title in session.execute(
            select(Chapter.chapter_id, Chapter.chapter_num, Chapter.chapter_title).where(
                Chapter.novel_id.in_({job.novel_id for job in jobs.values()})
            )
        )
    }

    seen_blobs: set[str] = set()
    for job_id in job_ids:
        job = jobs[job_id]
        stages = stages_by_job[job_id]
        yield {
            "type": "job",
            "job_id": str(job.job_id),
            "novel_id": str(job.novel_id),
            "status": "complete",
            "config": job.config,
            "start_chapter": job.config.get("start_chapter_num"),
            "end_chapter": (job.config.get("end_chapter_num") or 0) - 1,
            "condition": _condition(job, stages),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "stages": [{"stage_num": s.stage_num, "action": s.action, "config": s.config} for s in stages],
        }
        seen_chapters: set[UUID] = set()
        for stage in stages:
            for task in tasks_by_stage[stage.stage_id]:
                assert task.output_file_id is not None  # guaranteed by the finished-job filter
                for record in _read_records(object_store, object_keys[task.output_file_id]):
                    chapter_id = UUID(record["chapter_id"])
                    if chapter_id not in seen_chapters:
                        seen_chapters.add(chapter_id)
                        num, title = chapters_by_id[chapter_id]
                        yield {
                            "type": "chapter",
                            "job_id": str(job_id),
                            "chapter_id": str(chapter_id),
                            "chapter_num": num,
                            "chapter_title": title,
                        }
                    kind, content = _blob_content(record["payload"])
                    sha = hashlib.sha256(f"{kind}\0{content}".encode()).hexdigest()
                    if sha not in seen_blobs:
                        seen_blobs.add(sha)
                        yield {"type": "blob", "sha256": sha, "kind": kind, "content": content}
                    yield {
                        "type": "stream",
                        "job_id": str(job_id),
                        "chapter_id": str(chapter_id),
                        "stage": stage.stage_num,
                        "stream": record["stream"],
                        "data_name": record.get("data_name"),
                        "blob": sha,
                        "task_id": str(task.task_id),
                        "output_file_id": str(task.output_file_id),
                    }


def write_jsonl_gz(records: Iterator[dict[str, Any]], handle: BinaryIO) -> int:
    """Stream records as gzip-compressed JSON lines (fixed mtime, so equal records give equal bytes)."""
    count = 0
    with gzip.GzipFile(fileobj=handle, mode="wb", mtime=0) as archive:
        for record in records:
            archive.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode() + b"\n")
            count += 1
    return count


def _header_job_ids(source: BinaryIO) -> set[UUID]:
    with gzip.GzipFile(fileobj=source) as archive:
        header = json.loads(archive.readline())
    if header.get("type") != "header" or header.get("kind") != KIND:
        raise ValueError("Unexpected translation export header")
    return {UUID(value) for value in header["job_ids"]}


class LocalDestination:
    def __init__(self, root: Path) -> None:
        self.root = root / KIND

    def exported_job_ids(self) -> set[UUID]:
        exported: set[UUID] = set()
        for path in self.root.glob(f"*{SUFFIX}"):
            with path.open("rb") as source:
                exported.update(_header_job_ids(source))
        return exported

    def write(self, name: str, source: BinaryIO) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / name
        partial = path.with_suffix(".gz.partial")
        with partial.open("wb") as handle:
            shutil.copyfileobj(source, handle)
        partial.replace(path)
        return str(path)


class S3Destination:
    def __init__(self, bucket: str, prefix: str) -> None:
        options = _store_options()
        self.client: Any = boto3.client(
            "s3",
            endpoint_url=options["endpoint_url"],
            region_name=options["region"],
            aws_access_key_id=options["access_key_id"],
            aws_secret_access_key=options["secret_access_key"],
            config=options["config"],
        )
        self.bucket = bucket
        self.prefix = f"{prefix.strip('/')}/{KIND}/"

    def exported_job_ids(self) -> set[UUID]:
        exported: set[UUID] = set()
        pages = self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=self.prefix)
        for page in pages:
            for item in page.get("Contents", []):
                key = item["Key"]
                if key.endswith(SUFFIX):
                    with closing(self.client.get_object(Bucket=self.bucket, Key=key)["Body"]) as source:
                        exported.update(_header_job_ids(source))
        return exported

    def write(self, name: str, source: BinaryIO) -> str:
        key = f"{self.prefix}{name}"
        self.client.upload_fileobj(
            source,
            self.bucket,
            key,
            ExtraArgs={"ContentType": "application/jsonl", "ContentEncoding": "gzip", "ChecksumAlgorithm": "SHA256"},
        )
        return f"s3://{self.bucket}/{key}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export translation jobs finished since the last run into one translation_job.v1 file."
    )
    parser.add_argument(
        "--since", type=datetime.fromisoformat, help="include previously exported jobs finished after this time"
    )
    parser.add_argument("--bucket", default="analytics", help="destination bucket (default: analytics)")
    parser.add_argument("--prefix", default="exports", help="key prefix inside the bucket (default: exports)")
    parser.add_argument("--out", type=Path, help="write to this local directory instead of the bucket")
    args = parser.parse_args()

    destination = LocalDestination(args.out) if args.out else S3Destination(args.bucket, args.prefix)
    since = args.since or EPOCH
    exported = set() if args.since else destination.exported_job_ids()
    with SessionLocal() as session:
        until = session.scalar(select(func.now()))
        assert until is not None
        job_ids = [job_id for job_id in finished_job_ids(session, since, until) if job_id not in exported]
        if not job_ids:
            print(f"no jobs to export since {since.isoformat()}")
            return
        name = until.astimezone(UTC).strftime(NAME_FORMAT) + SUFFIX
        with tempfile.TemporaryFile() as spool:
            count = write_jsonl_gz(
                dump_translation_jobs(session, get_object_store(), job_ids, since=since, until=until), spool
            )
            spool.seek(0)
            target = destination.write(name, spool)
    print(f"wrote {target}: {len(job_ids)} jobs, {count} records")


if __name__ == "__main__":
    main()
