SELECT
    (j->>'job_id')::UUID AS job_id,
    $ingest_id::UUID AS ingest_id,
    (j->>'novel_id')::UUID AS novel_id,
    j->>'status' AS status,
    j->'config' AS config,
    (j->>'start_chapter')::INTEGER AS start_chapter,
    (j->>'end_chapter')::INTEGER AS end_chapter,
    j->'condition' AS condition,
    sha256(CAST(j->'condition' AS VARCHAR)) AS condition_hash,
    j->'stages' AS stages,
    (j->>'created_at')::TIMESTAMPTZ AS created_at
FROM records
WHERE j->>'type' = 'job'
