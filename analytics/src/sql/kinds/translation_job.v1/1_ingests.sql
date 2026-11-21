SELECT
    $ingest_id::UUID AS ingest_id,
    j->>'kind' AS kind,
    $file_sha256 AS file_sha256,
    j->'producer'->>'name' AS producer,
    j->'producer'->>'version' AS producer_version,
    json_object(
        'database', j->'producer'->'source'->>'database',
        'exported_at', j->'producer'->>'exported_at',
        'watermark', j->'watermark',
        'job_ids', j->'job_ids'
    ) AS source,
    $source_path AS source_path,
    $loader_version AS loader_version
FROM records
WHERE j->>'type' = 'header'
