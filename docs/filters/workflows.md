# Filter workflows

## Motivation

NovelTL began as a collection of Python scripts that sent individual novel
chapters to an LLM. Small context windows made chapter-by-chapter processing a
practical limitation, but the resulting translations lacked consistent,
reusable knowledge about names and other important terms.

Automatic labeling improved the input, but introduced its own noisy data:

- Low-score labels are often nonsensical or irrelevant, although some are
  valid.
- Ordinary nouns such as "scientist" or "airplane" may be detected even when
  they are not useful translation terms.
- Words that belong together may be separated into multiple labels.
- Unrelated words may be merged into one label.
- Model-provided categories are insufficient for domain-specific concepts such
  as cultivation techniques, cultivation levels, and novel-specific power
  systems.
- Rule-based discovery can recognize familiar genre patterns, but it is less
  effective when an author invents an original terminology system.

Correcting these problems is not always a matter of applying one predicate to
every label. A common word may have hundreds of occurrences. Reviewing every
occurrence wastes effort, while judging the word from only one context is
unreliable. A reviewer may instead inspect a random sample, use the observed
rate to decide the whole group, request more evidence, or escalate uncertain
occurrences to individual review.

Future workflows may also use an LLM as a judge, create glossary candidates,
or prepare typed actions other than deletion. The system therefore cannot be a
fixed sequence owned by a monolithic filter class.

A **workflow** models the in-progress analysis and review of a typed collection
of instances. Users incrementally apply compatible field and collection
operations. The system may record dependencies internally, but users do not
need to author a DAG or follow one universal linear pipeline.

## Workflow model

A workflow owns:

- A stable workflow identifier.
- Its NovelTL scope, including the novel and any source label group.
- The user who created it and relevant authorization information.
- A recursive instance schema.
- A materialized collection of instances conforming to that schema.
- The current grouping, sampling, review, and inclusion state.
- An append-only record of operations performed.
- A lifecycle status.
- An optional terminal application result.

The instance collection must be stored as independently addressable rows, not
as one list on the workflow record. Instances and groups must support
pagination from the first implementation.

Workflows are persistent so a large review does not have to be completed in one
browser session.

## Lifecycle

The lifecycle describes the workflow as a whole without prescribing a fixed
set of internal stages. Expected statuses include:

- `active`: operations or review may continue.
- `applying`: the terminal application operation is in progress.
- `completed`: application finished and its result is recorded.
- `failed`: an operation failed in a way that requires attention.
- `stale`: some source references are no longer valid for application.
- `deactivated`: the workflow was cancelled and archived without application.

Additional operational statuses may be introduced if asynchronous execution
requires them.

Deactivation is a first-iteration requirement. It stops further work, prevents
application, preserves enough audit information to explain what happened, and
removes the workflow from the default active-work list. Physical retention and
eventual deletion are separate policy decisions.

## Workflow operations

Operations are offered based on the current instance schema. A user should not
need to construct a graph manually: after each operation, the workflow exposes
the next compatible operations.

The foundational operation algebra includes:

### Map

Derive or transform nested fields using registered functions. Examples include
normalizing a label word, projecting a label to a text span, or retrieving
sentence context.

### Filter

Retain or exclude instances using recursively composed predicates over typed
key paths. Filtering should record inclusion state rather than immediately
delete the underlying workflow rows.

### Group

Partition instances by one or more derived values, such as exact label word,
normalized word, proposed category, or another filter-defined key.

Grouping is a collection operation. Group records and memberships should be
stored separately from instance payloads so groups can be paginated, sampled,
and reviewed efficiently.

### Sample

Select reproducible members from a collection or group. A stored sample
includes the selected instance identities and the selection parameters,
including a random seed when randomness is used.

Reviewers may request additional samples without losing earlier evidence.

### Aggregate

Calculate group-level statistics, such as occurrence count, score
distribution, reviewed count, or the percentage of sampled instances receiving
a particular decision.

### Flat map

Produce zero or more workflow instances from one input instance. This supports
future analytical transformations whose cardinality is not one-to-one. It does
not itself modify NovelTL labels.

### Annotate

Write permitted `Mutable<T>` fields, such as a reviewer comment,
classification, or decision. Immutable fields and NovelTL references cannot be
changed through annotation.

### Apply

Apply is the single terminal operation that may mutate NovelTL domain data. It
is described separately below.

## Context retrieval

Context retrieval is an ordinary typed mapping rather than a phase implemented
independently by every filter.

Canonical getters operate on semantic types:

- A sentence getter accepts a `TextSpan` and returns `SentenceContext`.
- A paragraph getter accepts a `TextSpan` and returns `ParagraphContext`.
- A chapter getter accepts an appropriate chapter or span reference and
  returns `ChapterContext`.
- A `LabelRef` can be explicitly projected to a `TextSpan` before using these
  getters.

Contexts may be materialized for all instances, loaded only for a sample, or
retrieved lazily during review. This choice depends on collection size and the
workflow's needs.

## Group and individual review

Both group-level and occurrence-level review are first-class requirements.

A group contains:

- Its typed grouping key.
- The total number of member instances.
- Stored samples and their review results.
- Aggregate statistics.
- A group-level disposition, when one has been made.

A reviewer may:

- Accept or reject an action for the whole group.
- Request more samples.
- Leave the group unresolved.
- Escalate the group to occurrence-level review.
- Override the group outcome for a specific occurrence.

When both levels contain decisions, an occurrence-level override takes
precedence over the group-level decision. Instances without either remain
unresolved and cannot be silently included in application.

The exact vocabulary of decisions is action-specific. A boolean "pass" value
is insufficient because it does not explain whether the resulting action will
remove, retain, reclassify, or promote an instance.

Human, rule-based, statistical, and LLM-assisted reviewers should ultimately
produce compatible typed review values. Where each kind of reviewer executes
is an implementation decision; human changes originate in the frontend and
must be persisted by the backend.

## Application

Application is always the final workflow operation. Earlier operations may
read NovelTL data and materialize immutable references, but they cannot modify
novels, chapter content, label groups, labels, or glossaries.

An application consumes a specific compatible data type and an explicit
action. Examples may eventually include:

- Removing referenced labels.
- Creating labels from reviewed text spans.
- Reclassifying referenced labels.
- Applying a reviewed merge or split plan.
- Promoting reviewed groups into glossary entries.

Application behavior belongs to the action and its accepted data type, not to
the filter or workflow that discovered the instances.

Copying to a new label group should be the safe default for actions that can
support it. Modifying an existing label group requires an explicit warning and
confirmation.

The application result must be persisted and include enough information to
audit and synchronize NovelTL, including:

- Which instances were attempted.
- Which succeeded, failed, or were stale.
- A reason for each failure.
- Affected NovelTL resource identifiers.
- Any newly created label group or other domain resource.

## Editing and staleness

NovelTL editing remains available while a workflow is active. The UI should
warn users that text or label edits within the workflow's scope may disrupt the
workflow, but it should not lock the novel for the lifetime of a persisted
review.

Staleness validation is mandatory:

- `TextSpan` and `LabelRef` values retain the immutable chapter-content
  identity from which they were created.
- A text edit creates a new chapter-content version; references to the old
  version are not redirected to the new version.
- Label edits or label-data replacement may likewise invalidate label
  references.
- Application checks every source reference before mutation.
- Stale instances must not be silently applied to newer content.

The first implementation may reject an application containing any stale
instance or report partial failures. The exact atomicity policy remains to be
decided, but staleness must always be visible to the user.

## Persistence, history, and failures

The first implementation does not require a complete immutable copy of every
instance at every operation. Such snapshots grow roughly with the number of
instances, their payload size, and the number of operations.

A practical initial model keeps:

- The current materialized instance payload.
- Current inclusion, grouping, sampling, and review state.
- An append-only operation log containing the registered operation and
  version, parameters, input and output paths, timestamps, counts, and errors.

This preserves auditability without requiring full revision snapshots. Exact
undo, branching, and replay behavior are open design questions.

Operations over large collections must:

- Execute in bounded batches or background jobs where appropriate.
- Record partial failures rather than losing the whole workflow state.
- Expose progress when work is not immediate.
- Remain safe to retry or otherwise prevent duplicate effects.

## User interface requirements

The frontend should present one workflow subsystem rather than a separate
top-level panel for every filter.

Shared UI handles:

- Active and archived workflow lists.
- Workflow status and progress.
- Schema-driven operation configuration.
- Paginated groups and instances.
- Sampling and review.
- Deactivation.
- Application preview, confirmation, and results.

The UI may use a renderer registry for semantic data types and complex
operations. Straightforward types use generic schema-driven controls; known
types such as labels, text spans, and sentence contexts receive purpose-built
renderers. A specialized workflow may replace part of the shared interface
without reimplementing persistence and lifecycle behavior.

## Example: low-score label cleanup

1. The user creates a workflow scoped to a novel and source label group.
2. The source operation materializes `LabelRef` instances.
3. A score predicate excludes labels above the chosen threshold.
4. A mapping normalizes each label word.
5. The instances are grouped by normalized word.
6. The user requests a random sample from each group.
7. Sampled labels are projected to text spans and enriched with sentence
   contexts.
8. The user reviews the evidence and accepts, rejects, requests more samples,
   or escalates a group.
9. Escalated occurrences receive individual decisions.
10. The user chooses a compatible terminal action, normally against a copied
    label group.
11. Application validates every reference, performs the approved mutations,
    and stores a structured result.

This workflow supports the original score-filter use case without making
score filtering responsible for context extraction, decisions, or label
deletion.

## Example: glossary candidates

1. Candidate label or text-span instances are grouped by a normalized term.
2. Frequency and other useful statistics are aggregated.
3. Sentence or paragraph contexts are sampled from each group.
4. A human or LLM-assisted reviewer judges whether the group represents a
   reusable translation term.
5. Uncertain groups receive more samples or occurrence-level review.
6. Accepted groups are passed to a glossary-promotion action.

This avoids reviewing every occurrence while retaining evidence and explicit
provenance for the group decision.

## Example: LLM-assisted judgment

An LLM judge is a reviewer, not a special kind of workflow. It consumes typed
instances and contexts and produces typed proposed decisions with model,
prompt, and parameter provenance. A human may accept, reject, or override those
decisions before terminal application.

The execution location, model interface, and approval policy for LLM judges
remain open.

## Open questions

- The exact source operations used to initialize workflows.
- The initial catalog of maps, predicates, groupers, samplers, aggregators,
  reviewers, and apply actions.
- Whether application is atomic for the complete workflow, per group, or per
  instance.
- How stale instances are refreshed or replaced when the user wants to
  continue a workflow.
- The retention and deletion policy for completed and deactivated workflows.
- The amount of operation history required for undo and deterministic replay.
- Which operations execute synchronously, in the current backend worker, or in
  a future independent workflow service.
- How trusted AI clients are authorized to create operations, submit reviews,
  and request application.
