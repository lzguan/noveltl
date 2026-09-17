# Translation UI layout

This is a proposed layout for discussion before frontend integration. The
wireframes describe information hierarchy and interactions rather than final
spacing or styling. Backend behavior is documented in [README.md](README.md).

## Trying the prototype

The edit page now includes a Translations tab in the right sidebar. It uses local
sample jobs and memory groups; creating jobs and using controls makes no backend
requests. State lasts while that novel's editor remains mounted.

Open the “Prototype · sample data, no jobs submitted” controls to advance running
stages manually, reset sample jobs, show an empty list, or simulate a dispatch
failure. Create job opens the stage builder with schema-driven configuration.
Conversion remains disabled until backend integration. Chapter ranges currently
use an inclusive end in the prototype.

## Placement

Proposed location: a **Translations** tab in the edit page's right sidebar,
alongside Autolabels, Filters, Memories, and Memory Agent. This location remains
to be confirmed. The panel is scoped to the novel being edited.

The panel contains a job list and a button at the top that opens the creation
dialog. Batch details open in a dialog; creation uses a separate dialog.

## Job list

```text
Translations
[ + Create job ]                              [ Refresh ]

+-------------------------------------------------------+
| Job #12                               Running [spinner]|
| Chapters 1-500 · 3 stages · 5 batches              [i] |
| [########------------] 40%                             |
| 1 batch complete · 2 running · 1 failed · 1 not started |
|                                                       |
| [ Start ] [ Resume ] [ Retry ] [ Cancel ]               |
+-------------------------------------------------------+

+-------------------------------------------------------+
| Job #11                                    Complete   |
| Chapters 1-100 · 1 stage · 1 batch                 [i] |
| [####################] 100%                            |
| [ Create novel from results ]                         |
+-------------------------------------------------------+

[ Previous ]                 Page 1 of 3        [ Next ]
```

Job numbers are illustrative display labels. A failed batch adds a warning
indicator even if other batches are still running. An empty list explains that
no jobs exist yet and keeps the Create job button available.

### Progress and status

The initial progress approximation is **completed tasks / total tasks**. A task
represents one batch at one stage. The bar measures completed pipeline steps,
not elapsed time or the proportion of chapters translated. Stages have equal
weight despite potentially different durations.

Use task status and failure fields to derive progress. Claim tokens are internal
worker ownership details and are not needed by the UI. A provider batch can be
processing while no worker holds a claim.

Distinguish not started, running, interrupted/resumable, failed, cancelled, and
complete states. Do not show a spinner merely because unfinished tasks exist.
Mixed jobs can show counts and both a running indicator and a failure warning.
Exact aggregate status rules and how to distinguish interruption from queued
work remain integration decisions.

### Job and batch controls

Expose **Start, Resume, Retry, and Cancel** at both job and batch scope. Disable
unavailable actions with an explanation. Job controls operate on eligible batches;
they should not imply that completed batches will restart.

| Control | Intended interaction |
| --- | --- |
| Start | Begin work that has not started. |
| Resume | Continue interrupted, nonfailed work. |
| Retry | Recover failed work using the backend's recovery rules. |
| Cancel | Stop further local processing of unfinished work. |

Cancellation currently fences local workers; it does not cancel provider-side
inference. Retry has known limitations for terminal provider failures and invalid
model output. This sketch does not expand the scope of that deferred backend work.

After a control action, refresh the displayed state. Surface dispatch failures
separately so the UI does not report that work started when queueing failed.

## Batch details dialog

Clicking the job's information button opens a scrollable dialog with its pipeline
and paginated batch list. Each
batch shows completed stages, its current action and step, errors, and controls.
The information button should have an accessible label such as “Show job details”.

```text
Pipeline: Prune memories -> Combine chapter -> Translate

Batch 1                                      Complete
[####################] 3 / 3 stages
[ Start ] [ Resume ] [ Retry ] [ Cancel ]   (disabled)

Batch 2                               Running [spinner]
[#############-------] 2 / 3 stages
Translate · Waiting for provider
[ Start ] [ Resume ] [ Retry ] [ Cancel ]

Batch 3                                        Failed !
[######--------------] 1 / 3 stages
Combine chapter · Could not download input
[ Show error ]
[ Start ] [ Resume ] [ Retry ] [ Cancel ]

[ Previous ]                 Page 1 of 2       [ Next ]
```

Batch numbers are sufficient for the initial prototype. Optional context can
include chapter count and minimum/maximum chapter numbers, computed in SQL rather
than returning every chapter association. A range is a span, not a promise that
every chapter number in it exists.

Load batch details on demand and paginate large lists. The job list should use
aggregate counts rather than downloading all tasks for every job.

## Create job dialog

```text
Create translation job                                  [x]

Chapters        [ From ____ ]  [ To ____ ]
Batch size      [ 100 ]

Memory group    [ None                                  v ]
Initial inputs: [Chapter]

Stages                                               2 / 5

+--------------------------------------------------------+
| 1  Translate                         [ Configure ] [x] |
| Qwen Plus · English                                    |
| Chapter -> Chapter                                     |
+--------------------------------------------------------+
                           |
                           v
+--------------------------------------------------------+
| 2  Translate                         [ Configure ] [x] |
| Qwen Flash · English · Custom instructions              |
| Chapter -> Chapter                                     |
+--------------------------------------------------------+

Add stage       [ Select compatible action              v ]
                                             [ Add stage ]

                                    [ Cancel ] [ Create job ]
```

The initial proposal creates a job without starting it. Users inspect the created
job in the viewer and then select Start. Whether to offer Create and start as
well remains open.

The chapter-range labels must make their bounds clear. The backend currently uses
an inclusive start and exclusive end; decide whether the UI exposes that directly
or converts a user-facing inclusive end before integration.

### Initial inputs and memory group

Chapter text is always available. Selecting a memory group makes both chapter and
memory inputs available to the first stage. The selector is scoped to the current
novel. For a first-stage action that consumes memories, the selection supplies its
`memory_group_id` configuration.

If changing the group selection would invalidate the pipeline, explain which
suffix must be removed before applying the change. Later stages consume the
preceding stage's output; the initial group does not make memories implicitly
available to every stage.

### Stage stack

- Maintain an ordered list of one to five stages.
- Append through a compatible-action dropdown and an Add stage confirmation button.
- Do not reorder or insert stages in the middle in this first version.
- Removing a stage removes it and every following stage. Confirm the affected
  suffix explicitly, for example “Remove stages 2-4?”.
- Display each stage's input/output types and a short configuration summary.
- Filter new actions by whether their required inputs are a subset of the available
  outputs. Exact type-set equality is not required.
- Apply first-stage eligibility separately: `combine_chapter` currently requires
  a preceding stage even when its required types are available.
- Disable creation while required configuration is missing or invalid.

For example, selecting a memory group enables this sequence:

```text
Chapter + Memories
        |
        v
Prune memories       -> Memories
Combine chapter      -> Chapter + Memories
Translate with memories -> Chapter
```

Combine chapter attaches the pinned source chapter to the preceding memories.
The visible type sequence helps explain why different actions become available
after each addition.

### Stage configuration

Each added stage has a Configure button. The initial proposal expands its fields
inside the stage card, keeping configuration within the creation dialog rather
than opening another modal.

```text
1  Translate                              [ Collapse ] [x]

Model             [ Qwen Plus                         v ]
Target language   [ English                             ]
Instructions      [                                     ]
                  [                                     ]
Advanced settings                                      v
  Temperature     [ Default                             ]
  Max output tokens [ Default                           ]
```

Action choices, compatibility, and forms should be driven by backend metadata:
action names, display labels, input/output signatures, first-stage eligibility,
and configuration schemas. Reuse the project's schema-driven form approach.
Memory-group selection at the top should not become a second conflicting field
in the first stage's configuration form.

## Backend integration follow-up

These are dependencies for implementation, not prerequisites for a mocked UI
prototype:

- Expose action metadata alongside the existing typed configuration schemas.
- Add a novel-scoped, paginated job-list endpoint with aggregated progress counts.
- Provide batch details on demand with pagination. The current job-detail endpoint
  already returns stages, batches, task statuses, and errors, but returns them all.
- Add per-batch Start and Resume routes. Job-level controls and per-batch Cancel
  and Retry already exist.
- Add conversion of completed chapter outputs into a novel. Decide completeness
  requirements, chapter numbering/title handling, and duplicate-conversion behavior.
  Only pipelines ending in chapter output can support this action.

Prototype states should include an empty list, unstarted job, running job, mixed
running/failed batches, cancelled job, completed job, and control dispatch failure.
