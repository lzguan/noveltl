# Memory-agent evaluation change log

Entries are ordered newest first. Detailed evidence belongs in a linked run
report. Planned changes should not be marked accepted before their stated
evaluation has completed.

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
