# Local evaluation logs

The memory-agent worker writes its append-only JSONL output into this directory
in the development Compose configuration. JSONL files are ignored by Git; run
reports reference them by path and memory-job ID.

Choose a descriptive filename through `MEMORY_AGENT_LOG_FILENAME`. The value
must be a filename ending in `.jsonl`, not a path; `MEMORY_AGENT_LOG_DIR`
controls the directory separately. Reusing a filename appends to the existing
file, which is useful only when runs are intentionally multiplexed.

Do not place novel source text in this directory. If logs are shared outside a
local development environment, review them first because complete agent
messages include the processed chapter text.
