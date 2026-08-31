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
checkpoint and run-config files are YAML. Generated run artifacts will use
JSON and JSONL.

## Local layout

- `novels/` contains private catalog V1 corpora.
- `checkpoints/` contains checkpoint sets and expected memories.
- `run-configs/` contains experiment definitions.
- `runs/` contains generated run artifacts.
- `logs/` contains imported or generated raw logs.
- `history/` contains previous local evaluation notes and reports.

Run `agent-eval paths` to print the resolved paths. The initial scaffold can
list and validate authored YAML. Corpus conversion, run execution, recovery,
reviewing, and reporting will be added as subsequent vertical slices.

## Commands

```bash
agent-eval checkpoint list
agent-eval checkpoint validate checkpoints/example.yaml
agent-eval config list
agent-eval config validate run-configs/example.yaml
agent-eval corpus list
agent-eval run list
agent-eval review list
agent-eval report list
```

