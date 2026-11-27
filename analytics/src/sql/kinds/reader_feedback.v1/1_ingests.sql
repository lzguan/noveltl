SELECT
    $ingest_id::UUID AS ingest_id,
    'reader_feedback.v1' AS kind,
    $file_sha256 AS file_sha256,
    'reader-api' AS producer,
    '1' AS producer_version,
    NULL::JSON AS source,
    $source_path AS source_path,
    $loader_version AS loader_version
