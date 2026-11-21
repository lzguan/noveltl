import argparse
import hashlib
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

import boto3
import duckdb
from botocore.config import Config

from .connection import connect

ROOT = Path(__file__).resolve().parents[1]
KINDS_DIR = Path(__file__).parent / "sql" / "kinds"
STAGING = ROOT / ".data" / "staging"  # mounted into the DuckDB server at /data/staging
SERVER_STAGING = "/data/staging"
NAMESPACE = uuid.UUID("6f1c2a52-6a0e-4b8e-9f7e-3d3b6a0c5e11")
SQL_NAME = re.compile(r"^\d+_(?P<table>[a-z_][a-z0-9_]*)\.sql$")
PARAM = re.compile(r"\$([a-z_][a-z0-9_]*)")


@dataclass(frozen=True)
class Kind:
    name: str
    tables: list[tuple[str, str]]  # (target table, SELECT over `records`), in load order

    @property
    def prefix(self) -> str:
        return f"exports/{self.name}/"


def load_kind(directory: Path) -> Kind:
    tables = []
    for path in sorted(directory.glob("*.sql"), key=lambda p: int(p.name.split("_", 1)[0])):
        match = SQL_NAME.match(path.name)
        if match is None:
            raise ValueError(f"{path}: expected <order>_<table>.sql")
        tables.append((match["table"], path.read_text()))
    if not tables:
        raise ValueError(f"{directory}: no SQL files")
    return Kind(directory.name, tables)


def available_kinds() -> dict[str, Kind]:
    return {path.name: load_kind(path) for path in sorted(KINDS_DIR.iterdir()) if path.is_dir()}


def _git_version() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        dirty = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--", "src"], capture_output=True, text=True, check=True
        )
    except OSError, subprocess.CalledProcessError:
        return "unknown"
    return sha.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
        region_name=os.environ.get("S3_REGION"),
        config=Config(s3={"addressing_style": os.environ.get("S3_ADDRESSING_STYLE", "auto")}),
    )


def stage_file(kind: Kind, path: Path, out_dir: Path, params: dict[str, str]) -> dict[str, int]:
    """Split one export file into a Parquet file per target table; returns the row count per table."""
    local = duckdb.connect()
    try:
        local.execute("CREATE TABLE records AS SELECT json AS j FROM read_ndjson_objects(?)", [str(path)])
        counts: dict[str, int] = {}
        for table, select in kind.tables:
            used = {name: params[name] for name in PARAM.findall(select)}
            local.execute(f"CREATE TABLE staged AS {select}", used)
            row = local.execute("SELECT count(*) FROM staged").fetchone()
            counts[table] = row[0] if row else 0
            local.execute("COPY staged TO ? (FORMAT parquet)", [str(out_dir / f"{table}.parquet")])
            local.execute("DROP TABLE staged")
        return counts
    finally:
        local.close()


def load_staged(remote: duckdb.DuckDBPyConnection, kind: Kind, server_dir: str) -> None:
    remote.execute("BEGIN")
    try:
        for table, _ in kind.tables:
            remote.execute(
                f"INSERT INTO {table} BY NAME SELECT * FROM read_parquet('{server_dir}/{table}.parquet') "
                "ON CONFLICT DO NOTHING"
            )
        remote.execute("COMMIT")
    except Exception:
        remote.execute("ROLLBACK")
        raise


def ingest(kinds: list[Kind], bucket: str) -> None:
    s3 = _s3()
    remote = connect()
    remote.execute("CONNECT remote")
    loader_version = _git_version()
    loaded = remote.execute("SELECT kind, file_sha256, source_path FROM ingests").fetchall()
    loaded_paths = {path for _, _, path in loaded}
    loaded_hashes = {(kind, sha): path for kind, sha, path in loaded}

    for kind in kinds:
        keys = sorted(
            item["Key"]
            for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=kind.prefix)
            for item in page.get("Contents", [])
            if item["Key"].endswith(".jsonl.gz") and f"s3://{bucket}/{item['Key']}" not in loaded_paths
        )
        if not keys:
            print(f"{kind.name}: nothing to ingest")
        for key in keys:
            source_path = f"s3://{bucket}/{key}"
            STAGING.mkdir(parents=True, exist_ok=True)
            download = STAGING / Path(key).name
            s3.download_file(bucket, key, str(download))
            try:
                file_sha256 = hashlib.sha256(download.read_bytes()).hexdigest()
                if (kind.name, file_sha256) in loaded_hashes:
                    print(
                        f"skipped {source_path}: same content as {loaded_hashes[kind.name, file_sha256]}; "
                        "delete one of them"
                    )
                    continue
                ingest_id = str(uuid.uuid5(NAMESPACE, f"ingest:{kind.name}:{file_sha256}"))
                out_dir = STAGING / ingest_id
                out_dir.mkdir(exist_ok=True)
                try:
                    params = {
                        "ingest_id": ingest_id,
                        "file_sha256": file_sha256,
                        "source_path": source_path,
                        "loader_version": loader_version,
                    }
                    counts = stage_file(kind, download, out_dir, params)
                    load_staged(remote, kind, f"{SERVER_STAGING}/{ingest_id}")
                finally:
                    shutil.rmtree(out_dir, ignore_errors=True)
            finally:
                download.unlink(missing_ok=True)
            loaded_hashes[kind.name, file_sha256] = source_path
            print(f"loaded {source_path}: " + ", ".join(f"{table} {n}" for table, n in counts.items()))


def main() -> None:
    kinds = available_kinds()
    parser = argparse.ArgumentParser(description="Load new export files into the analytics store.")
    parser.add_argument("kinds", nargs="*", help=f"kinds to load (default: all of {', '.join(kinds)})")
    parser.add_argument("--bucket", default="analytics")
    args = parser.parse_args()
    if unknown := [name for name in args.kinds if name not in kinds]:
        parser.error(f"unknown kind(s): {', '.join(unknown)}")
    ingest([kinds[name] for name in args.kinds] if args.kinds else list(kinds.values()), args.bucket)


if __name__ == "__main__":
    main()
