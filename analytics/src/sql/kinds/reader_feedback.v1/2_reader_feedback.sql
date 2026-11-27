SELECT
    (j->>'feedbackId')::UUID AS feedback_id,
    $ingest_id::UUID AS ingest_id,
    (j->>'novelId')::UUID AS novel_id,
    (j->>'chapterId')::UUID AS chapter_id,
    (j->>'chapterNum')::INTEGER AS chapter_num,
    j->>'contentHash' AS content_hash,
    j->>'externalVersion' AS external_version,
    j->>'kind' AS kind,
    j->'payload' AS payload,
    j->>'clientHash' AS client_hash,
    (j->>'createdAt')::TIMESTAMPTZ AS created_at
FROM records
