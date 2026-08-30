# Memory-agent evaluation change log

Entries are ordered newest first. Detailed evidence belongs in a linked run
report. Planned changes should not be marked accepted before their stated
evaluation has completed.

## 2026-08-30 — Exact `DONE` terminal output

- **Model and settings:** DeepSeek V4 Flash, low thinking
- **Toolsets and job parameters:** `glossary_terms`; fresh memory group for
  each run
- **Change:** replace the requested narrative final account with an exact
  `DONE` response after all justified tool calls finish.
- **Objective:** remove terminal prose that duplicates the recorded tool
  interaction without changing memory-curation behavior.
- **Primary metrics:** exact-match final outputs, total final-output characters,
  completed chapters, retry prompts, and provider-reported cost. Successful
  lifecycle writes by memory type and chapters with writes are descriptive
  measurements rather than acceptance thresholds.
- **Degradation guardrails:** all 10 chapters complete; every final output is
  exactly `DONE`; and no retry prompts occur. Semantically review every chapter
  against its source text and the baseline run. Compare relevant memories that
  were omitted, unsupported or incorrect memories that were added, unnecessary
  duplication or over-recording, memory-type/category/tool misuse, and whether
  updates to existing state used the appropriate lifecycle operation. Accept
  only if the changed run has no material regression in those areas; explain
  differences rather than treating the baseline as ground truth.
- **Corpora and chapter ranges:** `cn-xianxia-001`; one run covering chapters
  1–10 and one extension run covering chapters 1–20
- **Budget or stop condition:** maximum provider-reported cost of $0.03 per
  run; stop early if either of the first two completed chapters returns
  terminal prose other than `DONE`.
- **Baseline:** matched chapters 1–20 completed for $0.0364479416 with 12,741
  final-output characters, 181 tool calls, zero retry prompts, and 51 new
  memories.
- **Result:** jobs `1a4498ff-d7ba-4ed4-a638-f7d6c615f842` and
  `e6e1dfc2-584a-4b66-8088-4b4b7810917f` completed 30 chapters in total. All
  30 outputs were exactly `DONE`. In the matched 20-chapter comparison,
  final-output text fell from 12,741 to 80 characters and provider-reported
  cost fell 18%, from $0.0364479416 to $0.0297896424.
- **Observed shortcomings:** both changed runs produced schema-validation
  retries and incorrectly converted two `时辰` to two hours. Semantic review
  also found pagination-driven duplicate facts and cultivation-state forks,
  missed mutable-state updates, ordinary skill progress stored as facts,
  incomplete relation associations, and unresolved term variants. The
  20-chapter run did improve selectivity and correctly expired two obsolete
  gang affiliations.
- **Decision:** inconclusive — not ready for acceptance. Retain the prompt
  change as part of the working baseline while evaluating more direct memory
  quality improvements.
- **Reports and local artifact references:**
  [runs/2026-08-30-done-output.md](runs/2026-08-30-done-output.md); local log
  `docs/memory/agent-evals/logs/without-output.jsonl`

## 2026-08-29 — DeepSeek V4 Flash low-thinking baseline

- **Model:** DeepSeek V4 Flash, low thinking
- **Toolsets:** `glossary_terms`
- **Corpus:** `cn-xianxia-001`, chapters 1–100
- **Change:** none; this records the pre-change reference behavior.
- **Objective:** establish cost, write-volume, retrieval, and lifecycle
  measurements for one completed 100-chapter run.
- **Degradation guardrails:** not applicable to a baseline.
- **Result:** baseline recorded.
- **Observed shortcomings:** summarized in the linked run report.
- **Decision:** accepted as the reference run for the next isolated change.
- **Report:** [runs/2026-08-29-deepseek-v4-low-baseline.md](runs/2026-08-29-deepseek-v4-low-baseline.md)

## Entry template

Copy this section for a new evaluated change:

```markdown
## YYYY-MM-DD — Change name

- **Model and settings:**
- **Toolsets and job parameters:**
- **Change:**
- **Objective:**
- **Primary metrics:**
- **Degradation guardrails:**
- **Corpora and chapter ranges:**
- **Budget or stop condition:**
- **Baseline:**
- **Result:**
- **Observed shortcomings:**
- **Decision:** accepted | rejected | inconclusive
- **Reports and local artifact references:**
```
