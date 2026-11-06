# Naming quality observations

Exploratory run performed 2026-11-02 against merged PR #129. These are concrete
investigation cases, not a benchmark score or accepted prompt improvements.

## Evidence and scope

下班，然后变成魔法少女, chapters 1–49, one run configured with
`deepseek:deepseek-v4-flash-low` for recording and naming. Recording enabled core
glossary writers/readers, aliases, continuity, advanced gender facts/perceptions/
events, and transformation guidance. Artifact guidance and cultivation were off.

All 98 tasks completed on their first attempt. There were 83 glossary terms and
82 pending mappings; 19 naming stages skipped inference. Logged estimated cost
was $0.384621372 for recording and $0.064119984 for naming. Chapter 50 was stopped
by the user and excluded; do not classify that abort as a model failure.

The completed local job ID is `3ac561ef-42a8-4972-9fd2-6d690c25a898`, memory
group `9d21aa10-4a0b-435e-a5a9-ac76eeee8839`. These are environment-specific
identifiers, not seeded fixtures. Full output was saved locally under
`playwright-mcp-output/term-review-49-*`; those files and the source corpus are
not tracked and are not guaranteed to exist in a fresh checkout. Completed
result logs were in `docs/memory/agent-evals/logs/dsv4-flash-low-marks-v1.jsonl`.
Check the configured worker sink rather than assuming that filename elsewhere.

## Cases worth preserving

| Case | Observation | Investigate |
| --- | --- | --- |
| 种级 | Returned `Species-level`. Chapter 11 establishes 种、芽、叶、蕾、花 as seed-to-flower development. The correct older definition is linked to 开华, not 种级. | Delivery/retrieval of related definitions. The chapter-19 naming log queried 种级 definitions, mappings, and rank relations without finding that definition. |
| 国度 | Returned `Nation` despite established 魔法国度 → `Magical Kingdom`; chapter 29 refers to the same realm. No abbreviation alias joins them. | Abbreviation links and relevant established mapping selection. |
| Floral codenames | 翠雀 → `Larkspur`, 朝颜 → `Morning Glory`, 樱 → `Cherry Blossom`, but 白玫 → `Bai Mei`, 荼蘼 → `Tumi`, 小锦 → `Xiaojin`. | An explicit naming policy. Individual choices are not all objectively wrong; the mixed treatment is the issue. |
| 花园防卫战 | Stored term has a chapter-46 event but no mapping. Source writes `‘花园’防卫战`. | Internal quotation marks: matching is exact on raw text, and the stored term dropped them. |
| 矢车菊 | Chapter 25 and its recorded summary contain this old codename, but no glossary term/alias or mapping exists. | Recorder term coverage; naming cannot translate a term never requested. |
| 国度审查 | Recorded as an organization and translated `Kingdom Censorship`; source chapter 6 merely says the kingdom may review an incantation. | Term qualification and classification before judging translation alone. |
| 花牌 | Classified as an organization, though chapters 39/49 describe a certification distinction. | Upstream term kind accuracy. |

Ordinary names and many terms were reasonable, including 林昀 → Lin Yun,
方亭市 → Fangting City, 心之种 → Heart Seed, 心之花 → Heart Flower,
魔力构装 → Mana Construct, and 王庭 → Royal Court. No identical target strings
appeared among the 82 saved mappings. That does not prove identity handling or
source coverage is complete.

## Interpretation

Existing mappings remain stable by design, so an early bad choice can persist
after later explanatory chapters. Keep source-term extraction, context delivery,
translation accuracy, and editorial preferences separate when assessing a fix.
Do not silently correct the observed mappings and then report them as raw output.

The review inspected renderings and checked suspicious cases against source and
stored context. It did not exhaustively annotate every source term, generate
chapter translations, compare models, or establish a general accuracy rate.
Use faithful synthetic fixtures for deterministic matching/context regressions;
judge naming-policy or prompt changes with source-grounded live comparisons.

Artifact guidance has planned configs for Changsheng and LOTM in the local
evaluation workspace, but no corresponding completed evaluation was found in
this audit. Do not call it tuned on the strength of its short instruction block.
