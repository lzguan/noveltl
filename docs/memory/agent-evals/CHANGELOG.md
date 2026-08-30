# Memory-agent evaluation change log

Entries are ordered newest first. Detailed evidence belongs in a linked run
report. Planned changes should not be marked accepted before their stated
evaluation has completed.

## 2026-08-30 — Split glossary memory toolsets

- **Status:** infrastructure change; not yet evaluated as a memory-quality
  improvement
- **Change:** make term creation, definitions, relations, facts, and events five
  independently configurable toolsets. Give definitions, relations, and facts
  their own retrieval, creation, supersession, expiry, and instructions. Keep
  shared glossary context and source-language rules in one prompt block.
- **Objectives:**

  - Let a job enable only the glossary operations and memory types it needs.
  - Let later experiments change one memory type's instructions without also
    changing the others.
  - Preserve the prior behavior when all five toolsets are enabled, apart from
    replacing the generic term-memory expiry tool with type-specific expiry
    tools.

- **Expected side effects:**

  - Enabling fewer toolsets should expose fewer tools and less unrelated
    instruction text.
  - With all five enabled, changed tool grouping and tool names may still alter
    model behavior, token use, or retries. Treat those differences as a change
    to measure rather than assuming equivalence.

- **Validation:** compare at least one all-toolsets run against a matched run
  from before the split before using the split as the base for later prompt
  experiments. Record tool calls, retries, input and output tokens, elapsed
  time, writes by memory type, duplicate writes, and checkpoint quality.

## 2026-08-30 — Persisted memory marks and scoped term-memory search

- **Model and settings:** DeepSeek V4 Flash, low thinking
- **Toolsets and job parameters:** `glossary_terms`; fresh memory group for
  each naturalistic run
- **Change:** save a category mark on facts and relations instead of discarding
  it after the tool call. Let the agent narrow one term's memories by category
  or by text contained in the memory. Apply these filters before splitting the
  results into pages. Expose separate definition, relation, and fact tools
  instead of asking the model to construct a nested memory-type object.
- **Objectives:**

  - Reduce duplicate writes and several active memories that disagree about
    the same subject.
  - Return less irrelevant memory text to the model, especially when a term has
    more memories than fit on one page.
  - Continue making the necessary memory changes even with less context.
  - Write focused memories: one useful claim, no incidental details, only the
    terms involved, and `local`, `recent`, or `persist` only for as long as the
    claim warrants.
  - Reduce input-token growth and total cost over long runs.

- **Risks under evaluation:**

  - A filter may hide an older memory needed to spot a duplicate, conflict, or
    state change.
  - Filtering may require enough extra calls or reasoning that the run becomes
    more expensive overall.
  - The allowed relation categories may exclude a useful relationship or make
    the agent force one into the wrong category.
  - Fewer or shorter memories may mean lost information rather than better
    judgment.

- **Checkpoint method:** choose checkpoints from the source and completed
  baseline before looking at changed-run output. For each long run, choose at
  least eight of each kind; one chapter may count for more than one kind.

  - Busy chapters that should produce several changes or require difficult
    reasoning about identity, relationships, or changing facts.
  - Quiet chapters that should produce no memory or one narrowly focused
    memory.
  - Long-history chapters where a needed older memory would be beyond the first
    unfiltered page.

  For every checkpoint, write down required changes, reasonable optional
  changes, writes that would be wrong, relevant older memories, and whether the
  right action is create, supersede, expire, or no change. Compare the baseline
  and changed runs on:

  - how many required changes were made;
  - how many writes were justified by the source and glossary rules;
  - whether the agent chose the right create, supersede, expire, or no-change
    action;
  - whether type, category, term links, and `local`/`recent`/`persist` scope were
    correct;
  - whether the active memories were correct after the chapter;
  - how often quiet chapters correctly produced no writes; and
  - whether each memory contained one focused claim without event narration or
    incidental details.

- **Candidate `cn-mystery-001` checkpoints:** select exact chapters from these
  ranges after both 250-chapter baselines finish.

  - Opening and identity setup: chapters 1–7.
  - First potion and new abilities: chapters 31–34.
  - Tarot Club and separate Audrey/Alger viewpoints: chapters 42, 53–54,
    60–62, and 94–97.
  - Tris/Trissy identity and gender change: chapters 57, 64–67, and 124–129.
  - The `2-049` pursuit and fight: chapters 71–79.
  - The library lead and shooting of Sirius: chapters 103–108.
  - Old Neil's loss of control and its aftermath: chapters 131–134.
  - Derrick, the City of Silver, and the Sun material: chapters 139–148.
  - The Sun artifact and Klein becoming a Clown: chapters 159–171.
  - Later Tarot meetings and separate Audrey, Alger, and Derrick scenes:
    chapters 180–184, 218–223, and 237–240.
  - Volume 1 tension, final fight, deaths, resurrection, and the Clown smile:
    chapters 196–215.
  - Start of Volume 2, the move to Backlund, and the Sherlock Moriarty identity:
    chapters 214–224.
  - Quiet-chapter candidates include chapters 23, 28, 48, 89, 93, 103, 126,
    151, 158, 173, 180, 195, 203–206, 222, and 226. Keep only chapters that
    source review confirms should have zero or one narrow write.

- **Primary metrics:**

  - The checkpoint results above, shown separately for busy, quiet, and
    long-history chapters as well as together.
  - Facts and relations written with a valid and appropriate category.
  - How often the agent could have filtered a term with more than one page of
    memories, and how often it did.
  - Memory rows and text returned by retrieval, plus relevant older memories
    that the agent failed to find.
  - Duplicate writes, groups of similar active memories, and conflicting
    current-state memories.
  - Memory length as supporting information only; shorter is not automatically
    better.
  - Writes per chapter and chapters with no writes, for checkpoints and the
    whole run.
  - Tool calls, retries, and failures.
  - Input, output, reasoning, and cached tokens per chapter and per source-text
    token; total cost; elapsed time; and chapters per hour. Show totals and
    trends across chapter ranges.

- **Degradation guardrails:**

  - All chapters finish without a repeated tool-input error.
  - Automated tests prove that saved categories can be read back; category and
    text filters work separately and together; and filtering happens before
    pagination.
  - Every new fact and relation has an allowed and appropriate category.
    Definitions have no category.
  - Filtering causes no critical missed change. Overall checkpoint quality must
    remain within the range of the matched baselines, and every serious miss
    must still be reported separately.
  - There is no meaningful increase in memories containing several claims,
    incidental details, event narration, irrelevant term links, or a longer
    scope than necessary.
  - Less context or fewer writes count as improvements only if checkpoint
    quality also passes.
  - Average cost per source-text token must not exceed the matched baseline
    average. Show each run separately so variation is not hidden.

- **Corpora and chapter ranges:**

  - Automated service and tool tests with more than one page of memories for a
    term.
  - Smoke: `cn-mystery-001`, chapters 1–20.
  - First long comparison: `cn-xianxia-001`, chapters 1–100, matched to the
    existing reference run.
  - Second long comparison: `cn-mystery-001`, chapters 1–250, matched to the two
    baseline runs currently being recorded.
  - Test a third novel with a different structure before claiming the change
    works broadly, but only after both earlier comparisons pass.

- **Budget or stop condition:** maximum provider-reported cost of $0.05 for
  the 20-chapter smoke run and $0.25 for the first 100-chapter changed run.
  Establish a separate cap from the completed smoke data before starting the
  longer `cn-mystery-001` pair. Stop before another corpus or replica if a
  filter returns a memory that does not match it, categories are missing from
  successful fact or relation writes, or invalid tool input keeps recurring.
  If few terms grow beyond one page, say that the context-reduction objective
  was not tested instead of treating unchanged cost as success.
- **Baseline:** the earlier two 20-chapter runs are pilot data. Replace this
  section with the two in-progress `cn-mystery-001` chapter 1–250 baselines,
  jobs `042352e3-8775-47da-a91b-e5ef9530d16e` and
  `47b06aaf-413c-4044-9cb7-8c2948713a8b`, after both finish and the logs are
  complete.
- **Result:** pending
- **Observed shortcomings:** three pilot jobs using the discarded nested
  memory-type schema (`8ae3374c-c04c-4418-a967-de0b52b977aa`,
  `b0138ad8-559e-41f3-b537-c96004b3e1d3`, and
  `cfd4e126-2d2f-40c3-80b4-07deac34a6ad`) produced 35 rejected tool calls
  across 9 of their first 16 logged chapters. The model commonly flattened the
  category beside `memory_kind`, encoded the nested object as a string, or
  emitted an unquoted memory type. These jobs do not test the replacement
  split-tool interface.
- **Decision:** pending. The 20-chapter run is only a smoke test. Acceptance
  requires both longer comparisons. A broader claim also requires the third
  corpus. Lower context growth is not established unless the agent actually
  retrieves terms with more than one page of memories.
- **Reports and local artifact references:** baseline log
  `docs/memory/agent-evals/logs/dsv4-flash-low-baseline-mys-long.jsonl`;
  pre-split pilot log
  `docs/memory/agent-evals/logs/dsv4-flash-low-marks-v1.jsonl`; split-tool
  changed-run artifact pending

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
