# Memory-agent evaluations

> Historical evaluation notes: this directory predates the current harness and
> may contain outdated operational instructions. Use the
> [eval README](../../../agent-evals/README.md) for current commands and the
> [design history](../../../agent-evals/docs/design-history.md) for an abstract
> record of design decisions. Older reports are retained here for now.

This directory records behavioral evaluations of the memory agent. Its purpose
is to make prompt, tool-schema, retrieval, lifecycle, and model changes
comparable without treating anecdotal improvements as regressions or wins.

- [CHANGELOG.md](CHANGELOG.md) records each evaluated change and its verdict.
- [`runs/`](runs/) contains detailed reports when an entry needs more evidence
  than belongs in the change log.

## Corpus identifiers

Tracked reports use stable identifiers such as `cn-xianxia-001` instead of
novel titles. Language and broad structural traits may be recorded when they
are relevant to interpreting a result.

Keep the private identifier-to-title mapping in `corpora.local.md`. That file
is ignored by Git. Do not commit source novel text, recovered chapter text, or
large excerpts to this directory. Raw evaluation inputs must be obtained and
stored in accordance with their applicable licenses and terms.

Novel names are not themselves evaluation artifacts, but identifiers keep the
public reports focused and avoid unnecessarily publishing the composition of a
private corpus.

## Evaluation tiers

Use the least expensive tier capable of detecting the expected behavior:

1. A 10-chapter smoke run checks schema compatibility, retries, tool failures,
   and catastrophic behavioral changes.
2. A compact synthetic lifecycle corpus checks known transitions such as
   aliases, friendship becoming romance, false death, mutable cultivation,
   multiple bodies, and mistaken beliefs.
3. A 40- to 100-chapter development corpus measures naturalistic extraction,
   retrieval, and lifecycle behavior.
4. A structurally different contrast corpus checks that an improvement does
   not depend on one novel's genre or prose.
5. A holdout or long-horizon corpus is reserved for milestone decisions.

Keep one reference model fixed while evaluating prompt and tool changes. Test
additional foundational models only after a change passes the reference-model
evaluation.

## Required evaluation record

Define these fields before starting a behavioral run:

- **Change:** the single behavior-affecting change under evaluation.
- **Objective:** the measurable behavior expected to improve.
- **Primary metrics:** the measurements used to judge the objective.
- **Degradation guardrails:** behavior that must not regress beyond a stated
  threshold.
- **Corpora and ranges:** corpus identifiers and half-open or inclusive chapter
  ranges.
- **Budget or stop condition:** the maximum intended spend or early-abort rule.
- **Decision rule:** the conditions for accepting, rejecting, or escalating the
  change.

Afterward, record the exact model settings, toolsets, job parameters, job
identifiers, aggregate results, observed shortcomings, and verdict. The Git
history of the report provides source-revision provenance.

## Core measurements

Prefer context actually exposed to the model over cumulative database writes:

- input, output, reasoning, and cached tokens;
- provider-reported cost;
- wall-clock run duration and per-chapter latency or throughput, stating
  whether the measurement includes queue time and retries;
- unique memory rows and serialized memory text returned per chapter;
- retrieval pagination and repeated exposure;
- successful writes, retries, and failures by tool and memory category;
- supersession-chain continuity and active-state forks;
- qualifying candidates that were missed;
- writes that violate the enabled memory category;
- final-response text that does not contribute to memory work.

Report both per-chapter and per-source-token measurements when comparing works
with materially different chapter lengths.

## Artifacts

Raw JSONL logs are stored locally in [`logs/`](logs/) and are not committed. In
the development Compose configuration, that directory is mounted as the memory
agent worker's `logs` directory, so the existing
`MEMORY_AGENT_LOG_DIR=logs` setting writes JSONL output there. Set
`MEMORY_AGENT_LOG_FILENAME` to a descriptive `.jsonl` filename for each
evaluation run or group of deliberately multiplexed runs. Changing either
setting requires restarting the worker process. A run report should record
enough information to find its entries locally:

- log path;
- memory-job and memory-group identifiers when available;
- model and thinking configuration;
- corpus content version or checksum when one can be recorded safely.

If a shared artifact store is added later, reports should link to an immutable
artifact rather than copying model messages or novel text into Git.
