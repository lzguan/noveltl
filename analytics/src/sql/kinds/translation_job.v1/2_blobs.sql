SELECT
    j->>'sha256' AS sha256,
    j->>'kind' AS kind,
    j->>'content' AS content
FROM records
WHERE j->>'type' = 'blob'
