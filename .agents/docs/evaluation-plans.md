# Evaluation plans

Discussed directions, not an approved design. Evals now read from the
[analytics store](analytics.md); `agent-evals/` (the earlier memory-agent eval
framework) is to be retired. Chapter-translation behavior is in
[chapter translation](chapter-translation.md).

## Current state (2026-11-21)

- [pronoun_judge.py](../../analytics/src/evals/pronoun_judge.py) is the first
  Pydantic Evals dataset: cases from `chapter_data`, a task that returns the
  stored translation, a deterministic tic-rate evaluator, and a whole-chapter
  DeepSeek judge listing 他/她 mismatches. Results go to the ignored
  `analytics/.data/evals/`. Planting she-to-he flips in two chapters
  (17 and 14) returned 15 and 9 reports, some naming the wrong character, so
  recall is partial and counts are approximate. Next: paragraph-pair judging,
  gender/persona memories as context, low thinking, and the planted-error
  check as a standing canary.
- The user wants to try both Pydantic Evals and Inspect. Agreed split:
  deterministic metrics as SQL or Python over the store (a future `metrics`
  table); frameworks for LLM judges; Pydantic Evals also fits CI-style agent
  evals.
- Metric priorities discussed: term adherence and cross-chapter name drift,
  paragraph alignment and length ratio, then a blind pairwise judge once an
  A/B exists. Gender memories as an input (pronouns) and a banned-tic
  instruction are the planned first A/B experiments.
- Experiments need a frozen memory group (or a filter such as the tag prefix)
  so arms see identical memories, and a run spec fixing slice, shared config,
  one varied factor, and repeats.

## Framework: Pydantic Evals

The user wants to replace the custom scoring/reporting in `agent-evals/` with an
existing framework. Harbor was considered and rejected: it targets agents in
container sandboxes with verifier scripts (Terminal-Bench), not a stateful
pipeline against the backend's PostgreSQL. Pydantic Evals ships with the
already-used `pydantic-ai`; Inspect AI is the heavier alternative.

Mapping agreed in discussion:

- **Case:** a chapter interval of one novel, a frozen snapshot of audited
  memories/terms/conventions at the interval start, and the expected output for
  the stage under test. The novel goes in `metadata`.
- **Task:** the agent/pipeline configuration; one `dataset.evaluate(task)` is an
  experiment, and comparing reports is an A/B.
- **Evaluator:** runs per case on inputs, output, expected output, metadata, and
  spans; aggregates come from the report.
- **Short-form:** feed one stage audited inputs and compare to audited output.
  Stage N's audited output doubles as stage N+1's input.
- **Long-form:** one case runs a chained pipeline over a long range; the output
  must keep per-stage artifacts so evaluators can measure drift within the run.
  Repeat runs: identical naming runs differed on 9–21 of 82 terms.

Pitfalls: cases run concurrently and are assumed independent, but runs write to
the database, so each case/run needs its own memory group and capped
concurrency. Frameworks do not replace the stateful runner or corpus/checkpoint
authoring; `agent-evals` never built reviewing or reporting, which is what the
framework would supply.

## Proposed slices

1. Score existing translation-job outputs (no runner): term adherence,
   pronoun counts against source, request size. Decides whether Pydantic Evals
   fits before further investment.
2. A runner task that creates a translation job from an experiment config and
   waits for it, against a per-case memory group cloned from an audited snapshot.
3. An LLM judge given the source text, using a different model than the
   translator.
4. Port memory-agent scoring to evaluators; retire the old reporting path.
5. Evaluate the calibration loop below.

Unsettled: whether the runner uses the API or backend functions directly (as
`agent-evals` does); the audited-snapshot format.

Deferred cleanup: the versioned test-data catalog moved from
`backend/test_support/test_data/` to [backend/src/datasets](../../backend/src/datasets)
(commit `8903e1a`) so `agent-evals` corpora could import it. Besides
`agent-evals`, its importers are backend tests (`tests/conftest.py`,
`tests/fixtures/scenarios.py`, `tests/test_data_support/`) and test-data scripts
in `backend/scripts/`. When `agent-evals` is deleted, consider moving it back
under `test_support/`; first confirm nothing outside tests and scripts imports it.

## Calibration loop (sample → refine) × N → translate

Translate a few chapter intervals (about 5–10 chapters each, roughly 5% of the
novel, placed at arc starts rather than uniformly at random), have a reviewer
with source access propose convention and glossary changes, confirm on fresh
intervals, then translate the whole novel. Stop after one or two rounds.

Most of it can wrap existing translation jobs: one job per interval, and the
loader snapshots inputs at first run, so each round sees the latest
conventions. Gaps:

- Refinement writes memory-side data (conventions, glossary), so it is a memory
  stage or new job type, not a translation stage.
- Chaining needs job-to-job dependencies; none exist (see
  [follow-ups](memory-workflow-followups.md#dependencies-between-whole-jobs)).
- The loader includes pending conventions and term mappings, so pending
  proposals reach the next round's prompts immediately. Human approval between
  rounds would need an approved-only input option or a separate proposal state.

## Evidence from the first A/B (2026-11-14)

Environment-specific: dev database, `qwen-flash`, group "test 1" of the
381-chapter 下班，然后变成魔法少女 import, chapters 1–20 and 200–210, terms +
conventions versus terms + memories + conventions, no prune stage.

- Term map entries found verbatim in output: 87% in both arms for 1–20; 87%
  versus 90% for 200–210. Most misses were exact-substring retrieval of
  single-character terms (气, 势) inside unrelated words, curly-apostrophe
  variants, and short-name forms; the model ignored the spurious terms.
- Pronoun counts tracked source 他/她 in both arms. One chapter-9 passage used
  "he" for the transformed protagonist only in the memory arm, against source 她.
- Translate request size for 200–210: 200 KB versus 4,304 KB (about 560
  unpruned memories per chapter).

Limits: string-match and pronoun-count proxies only; no meaning, continuity, or
prose-quality judgment; single run per arm.

## Reader feedback (2026-11-17)

The user read chapters 1–30 of a modern-day romance novel (dev novel
`e33ee811…`, environment-specific) translated by `qwen-flash` through the batch
API with `terms` + `conventions` inputs and no memories: "pretty good", clearly
better than a year earlier, but lacking human touch and slang, especially in
dialogue. The user suspects the modern setting is the easy case (no invented
terminology or classical idioms). Untested levers: translate-stage style
instructions, per-character voice conventions, a stronger model.
