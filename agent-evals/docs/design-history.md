# Memory-agent design and evaluation history

This is a retrospective of the design discussion and early evaluation cycles,
not a specification or a benchmark report. Sections follow the order of the
discussion rather than assigning dates to decisions that were not dated.
Implementation details belong in the [memory data model](../../docs/memory/data-model.md);
commands and artifact locations belong in the [eval README](../README.md).

All examples below are synthetic or abstract. This record deliberately omits
source titles, character names, quotations, plot details, corpus identifiers,
and identifying run paths. Detailed evidence remains in private run artifacts.
Observed tendencies describe small development samples, not general model
capabilities or statistically established improvements.

## 1. Mixed results prompted a boundary review

Early runs produced both useful memories and inconsistent extraction. Better
prompts and tool guardrails were plausible remedies, but not assumed sufficient.
A hit-count system was proposed: agents could mark useful memories, and a
pruner could expire unused records or restore recently useful ones. This was
not adopted. Usefulness tracking does not itself establish factual correctness
or whether a state has actually ended.

The initial review also found overlapping toolsets and dependencies. Multiple
toolsets had not originally been designed for arbitrary composition. The
discussion moved toward a shared reading surface with individually scoped
writers, rather than expecting the agent to choose perfectly among overlapping
readers.

Questions about retiring basic event tools, introducing small mark-specific
event writers, and composing prompts from job parameters were not fully settled.
Generic-event expectations and untested system guidance were excluded from the
focused comparison rather than treated as obligations of unavailable tools.

## 2. Categories were narrowed without merging every fuzzy pair

The working principle became: examine whether a distinction changes storage,
retrieval, or lifecycle behavior before adding categories or merging them.
Shared retrieval can accommodate ambiguous boundaries without eliminating useful
writer distinctions.

- Generic character facts were limited to age/stage, species, abilities, and
  limitations. The broad `trait` category was retired.
- Abilities and limitations remained separate but became jointly retrievable.
  An intrinsic restriction belongs with its ability; an independent
  vulnerability can be a limitation. For example, a tool requiring fuel does
  not need a second record saying it cannot operate without fuel.
- Definitions describe general concepts, objects, and techniques. A person's
  particular access to or use of a capability can be a character fact.
- Appearance moved outside gender into a fixed set of physical attributes and
  recurring attire. Routine clothing changes, transient expressions, and
  incidental scene details were excluded.
- Cultivation became a separate character writer. A system writer was deferred.
- Gender retained distinctions between body, self-identity, presentation,
  observer perception, durable change rules, and bounded occurrences.

Examples were added to explain boundaries. Writers were kept narrow even when
their shared reader returned several domains. Read access was explicitly not
permission to mutate every returned record.

## 3. Retrieval gaps and missing narrative context were separated

Review of failures suggested at least two mechanisms:

1. A query under one name could miss facts stored under another name for the
   same individual.
2. A later chapter could be misinterpreted without recent narrative context,
   even when individual durable facts were available.

An abstract example is a person using an alternate identity: a reader might
retrieve no relationships under that name, or mistake a temporary appearance
for a permanent bodily change. These are different problems and need not have
the same remedy.

Two experiments followed: alias-aware retrieval and rolling chapter continuity.
Neither was intended to guarantee complete extraction or solve every category
and lifecycle problem.

## 4. Capabilities supplied the extension point

A custom runtime wrapper and functional toolset registration were considered
for adding instructions, structured output, and post-run behavior. Existing
Pydantic AI capabilities were selected instead. The interface refactor happened
before the two behavioral experiments.

Ordinary toolsets were wrapped as capabilities. Continuity used lifecycle hooks
and structured output. Features remained independently selectable, allowing
baseline, alias-only, continuity-only, and combined configurations without
maintaining separate application architectures.

## 5. The first alias and continuity implementations

### Alias-aware retrieval

Aliases initially used one flat relation category for pairwise identity
equivalence. Shared character and relation reads expanded through active links
and returned the links alongside the results.

The important invariants were:

- Do not merge or rename stored terms or facts.
- Preserve each returned record's original subject and mark. Two forms of one
  individual can have different heights or appearances.
- Follow only eligible identity links for the requested chapter and group.
- Bound transitive traversal and report truncation. The implementation uses
  limits of 32 reached terms and 64 edges; those limits do not bound the initial
  loading of active aliases from the database.
- Do not interpret legacy multi-participant alias records as an automatic
  clique of pairwise equivalent identities.

A dedicated alias writer owned alias lifecycle changes. Returning linked state
was intended to prevent empty-lookups from being mistaken for absence of known
facts, not to make the returned facts infallible.

### Rolling continuity

Continuity was stored as a separate summary memory rather than forced into
fact, relation, or event categories. Its structured output contains a nonempty
summary capped at 1,500 characters.

The handoff is appended after the chapter text in the user prompt. It uses only
the immediately preceding eligible chapter's summary, tied to that chapter's
current content version; it does not fall back to arbitrarily older summaries.
It is staged and committed with successful chapter-task completion.

Summaries are supporting context, not durable factual authority. They should
preserve unresolved context while distinguishing established facts from
beliefs and uncertainty. Source edits invalidating downstream summaries remain
a deferred concern beyond predecessor-version eligibility.

## 6. Repetition changed the interpretation of early results

The first inspected examples made alias retrieval look particularly promising.
Additional trials showed that both variants could help and both could fail.
The assessment was revised rather than treating the initial impression as a
settled verdict.

Trace review distinguished several outcomes:

- Correct retrieval can expose previously hidden identity context.
- An agent can retrieve correct evidence and still overwrite it with an
  incorrect interpretation.
- A summary can correctly describe a resolved problem without expiring the
  corresponding durable limitation.
- A summary can carry an erroneous inference forward.
- Recognizing two spellings locally does not guarantee writing the alias.

Repeated baselines also showed variation: some apparent improvements addressed
recurring baseline failures, but a failure was not guaranteed to occur on every
baseline run. Three independent trials became the practical screening default,
not a claim of precise reliability estimation.

Both implementations were merged while remaining optional. This consolidated
development; it did not establish that the combination was proven or should
automatically become the default for every job.

## 7. Identity semantics were refined

The discussion initially considered placing spelling, transformation, disguise,
and impersonation under one alias hierarchy. This was rejected because
impersonation is not identity equivalence, and transformation need not conceal
identity.

The implemented alias categories became:

| Category | Meaning |
| --- | --- |
| `alias.spelling` | Context-established orthographic variants of the same identity |
| `alias.persona` | Names, nicknames, codenames, or invented identities belonging to the individual |
| `alias.transformation` | A separately named transformed bodily form of the same individual |

Each write selects one category. Transformation takes precedence over persona
when both describe the same link. Existing flat aliases remain readable; no
bulk migration was adopted.

An alias identifies the individual across names. It does not describe whether
a disguise is currently active, who knows the connection, or the mechanism
that changes a body. Leaving a form or revealing a secret does not ordinarily
end the identity link.

Impersonation received a separate directional relation and writer. An actor
posing as another independently existing person remains distinct from that
target. Character-state reads expose active impersonations in a separate
paginated section, never traversing them as alias edges or importing the
target's facts into the actor's state. Beginning and ending an impersonation
can be represented by its lifecycle without requiring a separate event record
for every transition. Observer knowledge remains separate and largely deferred.

The spelling prompt was reinforced: record context-established equivalence,
rather than merely selecting a preferred spelling. Continuity instructions also
ask for supported links relied upon by the handoff to be recorded when the
alias writer is available. These are prompts, not enforcement mechanisms.

Automatic script-normalized candidate search was discussed but deferred to
avoid changing retrieval and prompting in the same experiment. If added, the
preferred approach is indexed normalized search keys, preserving original
terms, rather than bulk fetching and filtering every query. Script conversion
and pinyin matches would suggest candidates, not automatically prove identity.

## 8. Combined trials helped, but checkpoint interpretation also changed

Later combined trials showed encouraging results for retaining contextual
distinctions and updating a limitation when it ended. In inspected traces,
alias retrieval exposed the relevant record while continuity helped preserve
the meaning of the surrounding narrative. Alias-only results still varied.
The new categories did not eliminate source misinterpretation.

Two scoring assumptions were reconsidered:

### Eventual identity linking versus immediate linking

For long works, eventual consistent linking was accepted as a primary goal.
Early-chapter timing is still useful diagnostically when an error occurs
before the link exists, but immediate linking is not inherently required.
This does not establish a safe delay for every narrative or guarantee eventual
linking on unseen works.

### Information retained versus category matched

A named-form alias may be correct while a separate transformation rule is
absent. Some runs retained activation information in a character ability or an
item definition instead. A missing expected mark therefore need not mean the
agent forgot the mechanic entirely.

Agents also hesitated to infer gendered anatomy from a form's description.
Caution about unsupported anatomy can be appropriate even when a generic
physical transformation is clear. Evaluation should separately assess identity
linking, availability of the activation mechanic, and supported gender-specific
claims. A broader transformation writer was not implemented during this cycle.

Appearance omissions were often deliberate filtering under an instruction to
store only identifying features. The project reconsidered treating every
persistent but ordinary physical description as mandatory. Such coverage was
downgraded in interpretation relative to stronger correctness requirements:
for example, not converting an impression of fragility into an actual
incapacity, or an observer's mistaken theory into an established limitation.
This was a review decision, not a claim that every existing checkpoint file
had already been revised.

## 9. Evaluation workflow and the next stage

Worktrees enabled independent implementation and experiments. Corpora and
checkpoints could be shared while configs and outputs remained separate.
The runner gained configurable paths and package-local dotenv loading, with
existing environment variables taking precedence. Corpus-lock verification
was made portable across checkouts without ignoring content changes.

Operational conventions settled on:

- Keep a reference model fixed while comparing code and prompt changes.
- Version configs and preserve exact run artifacts; do not pool trials from
  different implementations as if they were repetitions of one condition.
- Run independent replicas from fresh memory. Chapters remain sequential
  within each replica; replica concurrency is configurable.
- Budget at the whole-run level, accounting for all replicas and in-flight
  calls. Cheap model calls do not remove the human cost of reviewing results.
- Broaden narrative structures before drawing broad conclusions, then screen
  additional models before funding a full model-by-configuration comparison.
- Use regression tests for deterministic tool, retrieval, and lifecycle
  contracts; use opt-in evaluations for stochastic model behavior.

The practical recommendation became a supervised pilot rather than continued
optimization against the same small checkpoint set. This is not validation for
unattended processing over an entire long work. Reviewable batches, memory
snapshots, correction, and reruns remain important safeguards.

Translation architecture is still undecided. The proposed comparison is forced
context injection versus agent-selected retrieval, with a no-memory control.
Use the same source, translator model, and memory snapshot, initially keeping
translation memory read-only. The ultimate criterion is improved translation
consistency and acceptable correction effort, not merely cleaner memory marks.
That downstream benefit has not yet been established by these memory tests.

## Open decisions

- General disguise state and observer knowledge beyond impersonation.
- Fully structured form-specific state and broader transformation mechanics.
- Job-dependent prompt composition and a system writer.
- Automatic spelling/pinyin candidate retrieval.
- Hit-based retention, pruning, and redemption.
- Broad legacy migration and downstream summary invalidation after source edits.
- Long-horizon reliability, broader model comparisons, and translation strategy.

Future entries should preserve the distinction between proposals, implemented
changes, observed evidence, and adoption decisions. Use invented examples and
qualitative findings here; keep source-derived evidence in private artifacts.
