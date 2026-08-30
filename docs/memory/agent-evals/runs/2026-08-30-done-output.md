# Exact `DONE` terminal-output evaluation

## Run identity

- **Date analyzed:** 2026-08-30
- **Corpus:** `cn-xianxia-001`
- **Model:** DeepSeek V4 Flash
- **Thinking:** low
- **Toolsets:** `glossary_terms`
- **Baseline job:** `4f4c32c6-36aa-4cdb-9414-9b0441f35820`
- **10-chapter job:** `1a4498ff-d7ba-4ed4-a638-f7d6c615f842`
- **10-chapter memory group:** `74464222-deed-49f2-b5ef-7f58ffa7b0b4`
- **20-chapter job:** `e6e1dfc2-584a-4b66-8088-4b4b7810917f`
- **20-chapter memory group:** `7b29edcf-6762-42b0-a5f1-fa9ea99ff7e4`
- **Local changed-run log:**
  `docs/memory/agent-evals/logs/without-output.jsonl`
- **Local baseline log:**
  `docs/memory/agent-evals/logs/2026-08-29-recovered-memory-agent-runs.jsonl`

## Change and objective

The shared prompt replaced its requested narrative final account with an exact
`DONE` response after all justified tool calls. The objective was to remove
redundant terminal prose without materially changing memory curation.

Captured instructions for every valid changed-run chapter contained the new
exact-output request and omitted the old narrative-account request.

## Terminal-output result

Both changed runs complied: all 30 of 30 final outputs were exactly `DONE`.
The 10-chapter run reduced final-response text from the matched baseline's 6,638
characters to 40. The 20-chapter run reduced it from 12,741 characters to 80.

This establishes that the prompt change reliably removes the redundant final
account. It does not establish an equally large cost reduction because
reasoning and tool interaction dominate generated output.

## Matched 20-chapter measurements

| Measurement | Baseline | Changed run | Difference |
|---|---:|---:|---:|
| Completed chapters | 20 | 20 | 0 |
| Exact `DONE` outputs | 0 | 20 | +20 |
| Final-response characters | 12,741 | 80 | -12,661 |
| Input tokens | 625,165 | 716,277 | +91,112 |
| Output tokens | 73,110 | 64,111 | -8,999 |
| Reasoning tokens | 53,894 | 49,386 | -4,508 |
| Cache-read tokens | 521,472 | 644,608 | +123,136 |
| Provider-reported cost | $0.0364479416 | $0.0297896424 | -$0.0066582992 |
| Requests | 72 | 83 | +11 |
| Tool calls | 181 | 164 | -17 |
| Retry prompts | 0 | 4 | +4 |
| Added terms | 36 | 34 | -2 |
| Successful new memories | 51 | 47 | -4 |
| Retrieval calls | 90 | 74 | -16 |
| Unique memory exposures | 219 | 168 | -51 |
| Returned memory-content characters | 19,428 | 17,996 | -1,432 |

Provider-reported cost fell by approximately 18%, but the changed run used 15%
more input tokens. It returned 23% fewer unique memories but only 7% less
memory text, so its exposed memories were more verbose on average. The lower
retrieval volume cannot be treated as an unqualified improvement because some
required context was missed.

## What improved

- Both runs eliminated final narrative output without a terminal-compliance
  failure.
- The 20-chapter run was more selective about temporary pain, ordinary items,
  and event-heavy biographical records that appeared in the baseline.
- It classified the medicinal plants `紫母地丁香` and `寒月草` as `species`
  rather than the baseline's less accurate `item` classification.
- It recorded useful definitions for `贡献点` and `闻香虫` and useful durable
  relationships involving adjacent herb farmers, gang rivalry, and medicine
  supply.
- In chapter 17 it correctly expired 薛勇's membership in 灵蛇帮 and 刀疤青's
  leadership of that gang after the text explicitly merged the gangs into
  道宫外事堂. The baseline left both obsolete relationships active.

## What regressed or remained unreliable

### Pagination and mutable state

The most consequential failures came from treating the first five returned
memories as the complete result even when `count` was larger:

- Chapter 11 created a second divine-sense fact because the original fact was
  outside the first page.
- Chapter 12 created a second immortality fact for the same reason.
- Chapter 15 created a new persistent `练气二层` fact instead of superseding
  the existing `练气一层` fact, leaving conflicting active cultivation states.

The baseline also created duplicate facts, but it handled cultivation,
appearance, and concealment updates more consistently. It superseded the
protagonist's qi-blood deficiency, cultivation level, and `敛息诀` capability.
The changed run missed or forked those state chains.

### Fact and definition quality

- Both changed runs translated `两个时辰` as “two hours” in the `保命丹`
  definition. Two `时辰` is approximately four modern hours. The repetition
  indicates a systematic error rather than isolated sampling noise.
- The 20-chapter run stored ordinary medical knowledge and `种植术` proficiency
  as `ability` facts despite the toolset's restrictions.
- Its chapter-11 divine-sense duplicate included the pill transaction where the
  ability was used, leaking an event into a durable fact.
- Its `道宫` definition emphasized chapter-specific harvest and spiritual-rice
  details rather than a canonical description of the organization.
- Its `紫母地丁香` definition incorrectly attached 林南音's three-month
  employment trial to the plant itself.

### Relations and term identity

- Some otherwise useful commercial relationships violate the current blanket
  prohibition against recording transactions or temporary cooperation. Their
  continuity value suggests that the policy needs categories rather than a
  universal exclusion.
- A 张管事 role memory was associated only with 张管事 even though its content
  described his relationship to 道宫 and the herb farmers.
- A business supersession in chapter 18 removed still-relevant parts of 薛勇's
  sales-agent relationship while adding the new production arrangement.
- The run created `健体术` and `锻体术` without resolving whether they are two
  names for the same technique. It likewise created both `道宫外事堂` and its
  shortened form `外事堂` without connecting them.

### Tool-schema compliance

The 10-chapter run generated three `memory_kind` validation retries. The
20-chapter run generated four: three creations in chapter 12 and one
supersession in chapter 18. In each case the tagged object was encoded inside a
string before the agent corrected it.

## Decision

**Inconclusive — not ready for acceptance.**

The exact terminal-output behavior is reliable and remains in the working
baseline. The semantic guardrail did not pass: the changed runs contain
material factual, pagination, and lifecycle failures, even though those
failures are not plausibly caused by replacing the final narrative account.
Evaluation should move to a direct memory-quality improvement before spending
more on this isolated prompt change.
