# Analytics store

Standalone project in [analytics/](../../analytics/) with no NovelTL imports:
a DuckDB file served by the compose `duckdb` service, filled from export files
that producers write to the Garage bucket `analytics`. Plain SQL, no ORM.
Evaluation directions are in [evaluation plans](evaluation-plans.md).

## Source map

| Concern | Code |
| --- | --- |
| Producer: finished translation jobs to JSONL | [export_db.py](../../backend/scripts/export_db.py) |
| Connection (attaches the server as `remote`) | [connection.py](../../analytics/src/connection.py) |
| Store DDL | [create_tables.sql](../../analytics/src/sql/create_tables.sql), applied by [create_schema.py](../../analytics/src/create_schema.py) |
| Loader runner | [ingest.py](../../analytics/src/ingest.py) |
| Per-kind record-to-table SQL | [sql/kinds/](../../analytics/src/sql/kinds/) |
| Read helper for evals | [chapters.py](../../analytics/src/chapters.py) |
| First Pydantic Evals eval | [pronoun_judge.py](../../analytics/src/evals/pronoun_judge.py) |

## Flow

1. `backend/: uv run python scripts/export_db.py` writes one gzipped JSONL file
   per run to `exports/translation_job.v1/<until>.jsonl.gz`. It exports jobs
   whose tasks are all complete and whose IDs are absent from previous export
   headers. Explicit `--since` bypasses this check to allow re-exports. Records: `header` (producer, git version with
   `-dirty`, watermark, job ids), then per job `job` (config, normalized
   `condition`), `chapter`, `blob` (`sha256`, `kind`, `content`; hash covers kind, NUL, and UTF-8 content,
   JSON as sorted compact JSON; once per run), and `stream` (stage, stream,
   `data_name`, blob hash, task and output-file ids). Metadata comes from six
   batched queries; only task output files are fetched per object.
2. `analytics/: uv run python -m src.ingest [kind ...]` lists `exports/<kind>/`,
   skips keys already in `ingests.source_path`, downloads and hashes each new
   file, and skips (with a warning) content whose hash is already loaded under
   another key. `ingest_id` is uuid5 of kind and file hash.
3. A local in-memory DuckDB loads the file as `records` (`read_ndjson_objects`,
   column `j`) and runs each `<order>_<table>.sql` SELECT in the kind folder,
   writing Parquet to `analytics/.data/staging/<ingest_id>/`, which the server
   sees as `/data/staging/`. `$name` parameters are bound locally.
4. On the server, one transaction runs `INSERT INTO <table> BY NAME SELECT *
   FROM read_parquet(...) ON CONFLICT DO NOTHING` per table in file order
   (foreign keys first), then staging is deleted.

A new source is a kind folder plus DDL, as long as it is JSONL. The store is
meant to be rebuildable from the bucket rather than migrated.

## Quack pitfalls (DuckDB 2.0)

- Bound parameters fail on the remote, both after `CONNECT` and through the
  attached name. `chapters.py` inlines values after parsing them as UUIDs, ints,
  or hex.
- `ON CONFLICT` through the attached name and statements that read and write
  the remote together fail; hence the staged-Parquet load.
- Python needs `pytz` to fetch `TIMESTAMPTZ` values.
- The server process is the single writer; run one loader at a time (two
  loaders would share a staging folder).

## Known limits

- `jobs.job_id` is the key, so a later re-export of the same job is ignored.
- Not exported: token usage and `finish_reason` (the backend does not record
  them), unfinished or failed jobs, memory groups.
- Every stage's output passes its inputs through, so streams for stage N>0
  repeat stage 0's inputs; stage 0 is what the model saw.
- `condition_hash` is the sha256 of the condition JSON as exported, so it
  changes if the exporter's normalization changes.
