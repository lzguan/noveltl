# DeepSeek V4 Flash low-thinking baseline

## Run identity

- **Date analyzed:** 2026-08-29
- **Corpus:** `cn-xianxia-001`
- **Range:** chapters 1–100 inclusive
- **Model:** DeepSeek V4 Flash
- **Thinking:** low
- **Toolsets:** `glossary_terms`
- **Memory job:** `4f4c32c6-36aa-4cdb-9414-9b0441f35820`
- **Memory group:** `80564744-87c3-4b35-b9de-a44d6d76751f`
- **Local log:** `docs/memory/agent-evals/logs/2026-08-29-recovered-memory-agent-runs.jsonl`

The local JSONL file contains multiple runs. Filter it by the memory-job ID
above before calculating this run's measurements.

## Purpose

This is an observational baseline, not an evaluation of a new change. It
captures the state before introducing terse completion output, persisted
memory categories, or required relation categories.

## Usage and cost

| Measurement | Value |
|---|---:|
| Completed chapters | 100 |
| Input tokens | 3,833,355 |
| Output tokens | 425,270 |
| Reasoning tokens reported in usage details | 321,358 |
| Cache-read tokens | 3,239,680 |
| Provider-reported cost | $0.211261204 |
| Final-response characters | 61,310 |

The final-response text is redundant with the recorded tool interaction and is
a candidate for replacement with an exact `DONE` response.

## Successful new memory writes

| Memory type | Writes |
|---|---:|
| Definition | 69 |
| Relation | 93 |
| Fact | 79 |

There were also 36 successful fact supersessions, including 26 cultivation
level supersessions. Counts alone did not establish lifecycle quality: a model
can supersede frequently while still creating parallel active state.

## Fact context exposed to the model

These measurements count unique fact rows actually returned by successful
`term_memories` calls, not every fact stored in the database.

| Measurement | Value |
|---|---:|
| Unique fact exposures across the run | 469 |
| Average unique facts returned per chapter | 4.69 |
| Total returned fact-content characters | 34,688 |
| Average returned fact-content characters per chapter | 347 |
| Chapters 91–100: average unique facts | 5.8 |
| Chapters 91–100: average fact-content characters | 328 |
| Chapter 100 unique facts | 7 |
| Chapter 100 fact-content characters | 557 |

This is the primary baseline for future changes intended to reduce context
growth. Total created memories are retained as a diagnostic measurement, not
the cost-relevant success metric.

## Observed behavior

- The run made 69 successful new-definition writes. Three terms were associated
  with more than one new definition: one term in chapters 1 and 77, one in
  chapters 56 and 97, and the main character twice in chapter 83. Both chapter
  83 writes primarily defined a different associated term.
- The run made 93 successful new-relation writes. A keyword-assisted screen
  identified 18 writes containing transaction, co-location, or
  action/performance language. Examples include a profit-sharing sales
  arrangement in chapter 17, shared courtyard residence in chapter 37, a
  talisman-success comparison in chapter 42, and punishment at a location in
  chapter 58.
- The run made 79 successful new-fact writes, compared with 61 in the matched
  non-thinking run. It returned 469 unique fact rows containing 34,688 content
  characters, compared with 430 rows containing 43,446 characters in the
  non-thinking run.
- Retrievals for the main character in chapters 82, 83, and 87 each returned
  three fact rows. The returned cultivation text changed from main body at Qi
  Refining layer 8 in chapter 82, to main body at Great Perfection with split
  soul at layer 6 in chapter 83, to main body at Great Perfection with split
  soul at layer 9 in chapter 87. Chapter 95 returned three fact rows, including
  the main body at Foundation Establishment; chapter 99 returned two fact rows,
  including the split soul at layer 6.
- New-fact writes exceeded the instructed maximum of two in 2 of 100 chapters:
  chapter 1 produced three and chapter 64 produced six. The other 98 chapters
  produced at most two new facts.

## Observed shortcomings

- Final summaries contributed 61,310 characters without adding information not
  already present in the recorded interaction.
- Relation writes had no persisted category and included transactions,
  co-location, performance comparisons, and event state alongside useful
  aliases, kinship, mentorship, ranks, and memberships.
- The per-chapter fact limit usually held, but it did not guarantee global
  sparsity or prevent parallel mutable-state memories.
- Supersession counts did not reveal whether a canonical state formed one
  continuous chain or forked into multiple active memories.
- Some definitions were associated with incidental terms, inflating apparent
  definition multiplicity even when only one term was being defined.
- Cost-relevant retrieval measurements required offline JSONL analysis rather
  than being produced automatically with the run.
