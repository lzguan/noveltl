SELECT
    (j->>'job_id')::UUID AS job_id,
    (j->>'chapter_id')::UUID AS chapter_id,
    (j->>'stage')::INTEGER AS stage,
    j->>'stream' AS stream,
    coalesce(j->>'data_name', j->>'stream') AS data_name,
    j->>'blob' AS blob,
    (j->>'task_id')::UUID AS task_id,
    (j->>'output_file_id')::UUID AS output_file_id
FROM records
WHERE j->>'type' = 'stream'
