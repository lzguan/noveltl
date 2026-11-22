import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import duckdb

from .connection import connect


@dataclass
class ChapterData:
    job_id: uuid.UUID
    condition_hash: str
    condition: dict[str, Any]
    novel_id: uuid.UUID
    chapter_id: uuid.UUID
    chapter_num: int
    chapter_title: str | None
    streams: dict[tuple[int, str], Any] = field(default_factory=dict)  # (stage, data_name) -> text or parsed JSON

    @property
    def last_stage(self) -> int:
        return max(stage for stage, _ in self.streams)

    @property
    def source(self) -> str:
        return self.streams[0, "chapter"]

    @property
    def output(self) -> str:
        return self.streams[self.last_stage, "chapter"]

    def stage(self, stage: int) -> dict[str, Any]:
        return {name: value for (s, name), value in self.streams.items() if s == stage}


def _uuids(values: Iterable[str | uuid.UUID]) -> str:
    return ", ".join(f"'{uuid.UUID(str(value))}'" for value in values)


def _ints(values: Iterable[int]) -> str:
    return ", ".join(str(int(value)) for value in values)


def chapter_data(
    con: duckdb.DuckDBPyConnection,
    *,
    job_ids: Iterable[str | uuid.UUID] | None = None,
    novel_id: str | uuid.UUID | None = None,
    condition_hashes: Iterable[str] | None = None,
    chapters: Iterable[int] | None = None,
) -> list[ChapterData]:
    """
    Fetch every stream of the matching (job, chapter) pairs, ordered by job then chapter number.

    Args:
        con: Connection from `connection.connect()` (the store attached as `remote`, not CONNECTed).
        job_ids: Only these jobs.
        novel_id: Only jobs on this novel.
        condition_hashes: Only jobs with these condition hashes (hex prefixes are fine).
        chapters: Only these chapter numbers, e.g. `range(1, 21)`.
    Returns:
        One `ChapterData` per matching chapter of each matching job.
    """
    filters = ["TRUE"]
    if job_ids is not None:
        filters.append(f"j.job_id IN ({_uuids(job_ids) or 'NULL'})")
    if novel_id is not None:
        filters.append(f"j.novel_id = '{uuid.UUID(str(novel_id))}'")
    if condition_hashes is not None:
        prefixes = [h.lower() for h in condition_hashes]
        if not prefixes:
            return []
        if any(not all(c in "0123456789abcdef" for c in h) for h in prefixes):
            raise ValueError("condition hashes must be hex")
        filters.append("(" + " OR ".join(f"starts_with(j.condition_hash, '{h}')" for h in prefixes) + ")")
    if chapters is not None:
        filters.append(f"ch.chapter_num IN ({_ints(chapters) or 'NULL'})")

    rows = con.execute(f"""
        SELECT j.job_id, j.condition_hash, CAST(j.condition AS VARCHAR), j.novel_id,
               ch.chapter_id, ch.chapter_num, ch.chapter_title,
               s.stage, s.data_name, b.kind, b.content
        FROM remote.jobs j
        JOIN remote.chapters ch ON ch.job_id = j.job_id
        JOIN remote.streams s ON s.job_id = ch.job_id AND s.chapter_id = ch.chapter_id
        JOIN remote.blobs b ON b.sha256 = s.blob
        WHERE {" AND ".join(filters)}
        ORDER BY j.job_id, ch.chapter_num, s.stage, s.data_name
    """).fetchall()

    result: dict[tuple[uuid.UUID, uuid.UUID], ChapterData] = {}
    for job_id, cond_hash, condition, novel, chapter_id, num, title, stage, name, kind, content in rows:
        item = result.get((job_id, chapter_id))
        if item is None:
            item = result[job_id, chapter_id] = ChapterData(
                job_id, cond_hash, json.loads(condition), novel, chapter_id, num, title
            )
        item.streams[stage, name] = json.loads(content) if kind == "json" else content
    return list(result.values())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Print what is stored for some chapters.")
    parser.add_argument("--job", action="append", dest="job_ids")
    parser.add_argument("--novel")
    parser.add_argument("--chapters", help="e.g. 1-20,200")
    args = parser.parse_args()
    nums = None
    if args.chapters:
        nums = []
        for part in args.chapters.split(","):
            lo, _, hi = part.partition("-")
            nums.extend(range(int(lo), int(hi or lo) + 1))
    for item in chapter_data(connect(), job_ids=args.job_ids, novel_id=args.novel, chapters=nums):
        sizes = {
            f"{stage}:{name}": len(json.dumps(value, ensure_ascii=False))
            for (stage, name), value in item.streams.items()
        }
        print(f"job {str(item.job_id)[:8]} cond {item.condition_hash[:8]} ch {item.chapter_num}: {sizes}")
