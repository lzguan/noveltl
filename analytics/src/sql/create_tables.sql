CREATE TABLE IF NOT EXISTS ingests (
    ingest_id UUID PRIMARY KEY,
    kind TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    producer TEXT NOT NULL,
    producer_version TEXT NOT NULL,
    source JSON,
    source_path TEXT,
    loader_version TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (kind, file_sha256)
);

CREATE TABLE IF NOT EXISTS blobs (
    sha256 TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('text', 'json')),
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id UUID PRIMARY KEY,
    ingest_id UUID NOT NULL REFERENCES ingests (ingest_id),
    novel_id UUID NOT NULL,
    status TEXT NOT NULL,
    config JSON NOT NULL,
    start_chapter INTEGER,
    end_chapter INTEGER,
    condition JSON NOT NULL,
    condition_hash TEXT NOT NULL,
    stages JSON NOT NULL,
    created_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chapters (
    job_id UUID NOT NULL REFERENCES jobs (job_id),
    chapter_id UUID NOT NULL,
    chapter_num INTEGER NOT NULL,
    chapter_title TEXT,
    PRIMARY KEY (job_id, chapter_id)
);

CREATE TABLE IF NOT EXISTS streams (
    job_id UUID NOT NULL REFERENCES jobs (job_id),
    chapter_id UUID NOT NULL,
    stage INTEGER NOT NULL,
    stream TEXT NOT NULL,
    data_name TEXT NOT NULL,
    blob TEXT NOT NULL REFERENCES blobs (sha256),
    task_id UUID NOT NULL,
    output_file_id UUID NOT NULL,
    PRIMARY KEY (job_id, chapter_id, stage, stream, data_name)
);
