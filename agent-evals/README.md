# NovelTL agent evaluations

Local tools for defining, running, reviewing, and comparing memory-agent
evaluations. Evaluation inputs and results are intentionally excluded from
Git; only the framework and its tests are tracked.

## Setup

The project uses the backend as an editable dependency, so every new runner
process imports the current backend source without rebuilding the memory-agent
worker image.

```bash
uv sync --project agent-evals
uv run --project agent-evals agent-eval --help
uv run --project agent-evals agent-eval ui
```

The terminal UI and CLI use the same schemas and storage services. Authored
checkpoint and run-config files are YAML. Generated run artifacts use JSON.

## Local layout

- `novels/` contains private catalog V1 corpora.
- `checkpoints/` contains checkpoint sets and expected memories.
- `run-configs/` contains experiment definitions.
- `runs/` contains generated run artifacts.
- `logs/` contains imported or generated raw logs.
- `history/` contains previous local evaluation notes and reports.

Run `agent-eval paths` to print the resolved paths. Corpus, checkpoint, and
run-config authoring are available through both the CLI and terminal UI. Run
execution is available through the CLI. Recovery, reviewing, and reporting
will be added as subsequent vertical slices.

## Commands

```bash
agent-eval corpus import tmp/novel.json --id cn-fantasy-001 \
  --title "Private evaluation novel" --language zh
agent-eval corpus validate cn-fantasy-001
agent-eval corpus show cn-fantasy-001
agent-eval checkpoint list
agent-eval checkpoint create opening --corpus cn-fantasy-001 \
  --start 1 --end 3 --activity busy
agent-eval checkpoint metric set opening --id protagonist-identity \
  --memory-type fact --category identity --term 林渊 \
  --content "The protagonist reveals his identity." --lifecycle create
agent-eval checkpoint show opening --json
agent-eval checkpoint validate opening
agent-eval config toolsets
agent-eval config models
agent-eval config create marks-single-query-v1 \
  --change "Restrict retrieval to one mark per call" \
  --objective "Reduce wasted context" \
  --guardrail "Preserve checkpoint coverage" \
  --decision-rule "Accept if context falls without coverage loss" \
  --corpus cn-fantasy-001 --start 1 --end 250 \
  --checkpoint opening --model deepseek:deepseek-v4-flash-low \
  --toolset glossary_terms \
  --toolset glossary_character_read --toolset glossary_character_write
agent-eval config show marks-single-query-v1
agent-eval config update marks-single-query-v1 --replicas 3 --max-parallel 2
agent-eval config validate marks-single-query-v1
agent-eval run start marks-single-query-v1
agent-eval corpus list
agent-eval run list
agent-eval review list
agent-eval report list
```

`corpus import` accepts either an existing single-novel catalog directory or the
same bulk chapter upload JSON accepted by the backend's `/chapters/upload`
endpoint. Uploads preserve chapter numbers, titles, visibility, and source text.
Title and language are required because the upload document does not contain
novel metadata.

Each checkpoint YAML file describes one inclusive chapter range. Its
`expected_memories` are the individual review metrics for that range. The
`checkpoint metric set` command adds a metric or replaces the metric with the
same ID, making it safe to use for repeatable scripted edits. Use `checkpoint
update`, `checkpoint metric remove`, and `checkpoint delete --yes` for the
remaining non-interactive edits. Checkpoint writes verify that the selected
corpus exists and that the chapter range falls within it.

Run configs select individual checkpoints and toolsets. Toolset choices are
read from backend-owned memory-agent metadata through the editable backend
dependency, and the full agent verifies that its runtime registry matches that
metadata. The CLI and terminal UI therefore need no separate toolset list.
Toolset-specific settings remain in the YAML schema but do not yet have an
authoring interface.

## Running an evaluation

Export `DEEPSEEK_API_KEY` and `AGENT_EVAL_DATABASE_URL`, then start a saved
configuration:

```bash
export AGENT_EVAL_DATABASE_URL='postgresql://user:password@database:5432/postgres'
uv run --project agent-evals agent-eval run start marks-single-query-v1
```

`DB_URL` is used as a fallback when `AGENT_EVAL_DATABASE_URL` is unset. The
database role must be allowed to create and drop databases. Each replica gets
a UUID-named temporary PostgreSQL database, and the runner drops it after
capturing the final memory state. Chapters run sequentially within a replica;
`max_parallel` controls how many isolated replicas run concurrently.
The runner creates a real memory job and consumes the same `run_all_tasks()`
iterator as the production worker. A configured retry resets the failed task to
pending and resumes through a new production iterator.

The runner writes to `runs/<config-id>/<run-id>/`:

- `config.yaml` is the exact validated configuration used by the run.
- `run.json` records status, corpus fingerprint, timing, aggregate usage, and
  replica outcomes.
- `replicas/replica-NNN/replica.json` records progress and terminal status.
- Each chapter attempt is saved under the replica's `chapters/` directory,
  including messages, output, usage, timing, or failure details.
- `memory.json` contains the replica's final terms, memories, marks, and
  associations.

Cost and wall-time budgets are checked between chapter calls. Concurrent calls
already in progress can therefore finish after a budget is reached.

While a run is active, the CLI prints its artifact directory immediately and
reports replica lifecycle, chapter successes and failed attempts, and
cumulative provider-reported cost. The JSON artifacts remain the durable source
of truth.
