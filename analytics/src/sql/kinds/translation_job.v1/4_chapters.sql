SELECT
    (j->>'job_id')::UUID AS job_id,
    (j->>'chapter_id')::UUID AS chapter_id,
    (j->>'chapter_num')::INTEGER AS chapter_num,
    j->>'chapter_title' AS chapter_title
FROM records
WHERE j->>'type' = 'chapter'
