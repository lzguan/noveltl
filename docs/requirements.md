# Requirements for the edit novels page (STC)

Emphasis on STC. The design will likely be revised once a prototype is built.

## Motivation

Before we begin with the discussion of the UI, we should consider some of the potential pain points when performing automated translation of a novel. These are lessons learned from the ancient times of command line translation (circa. 2025).

A high level overview of the process to translating novels via the command line goes something as follows:

1. Run a Named Entity Recognition (NER) program to label and store the locations and other metadata of each name occuring in the novel.
2. Pass the raw label data through some filters to eliminate poor label guesses (e.g. eliminate labels below a certain score, merge labels that appear next to each other, split labels that are composed of two other existing labels).
3. Aggregate the remaining labels into a glossary of unique terms.
4. Perform manual editing on the glossary. This step is performed with the assistance of an LLM.
5. Feed each chapter of the novel along with words in the glossary that appear in that chapter into an LLM and ask it to provide translations of each word.
6. Aggregate the translations of the words and build a dictionary of original word : translated word.
7. Perform manual editing on the dictionary. This step is performed with the assistance of an LLM.
8. Feed each chapter of the novel, along with the words in the dictionary that appear in that chapter and their translations, and obtain translations.

Keep in mind that the intended user is someone with minimal to no knowledge of the source language. As such, steps 4 and 7 must be performed with the assistance of an LLM (or skipped, if the user is lazy). If the human has working knowledge of the written language, this step can be expedited significantly. Especially in step 4, this creates a problem where if the user does not have a definite test to determine the false positives returned from these steps and must trust the LLM's word. 

The risk of the LLM being wrong can be significantly reduced by providing context for the text around a word that we wish to check. Doing this manually, however, is rather time consuming and can easily take longer than the other steps combined. It would hence be best if there was some functionality that could find all contexts for a given word.

Step 2 also presents a significant failure risk. For one, a text with the words "George lives in Washington, a city in a country founded by George Washington" could be labelled as "`George` lives in `Washington`, a city in a country founded by `George Washington`". When performing merge/split operations, there is a possibility that the label `George Washington` gets split up into two labels: `George` and `Washington`. This issue is compounded in Chinese as there are no spaces in that language.

A potential solution is to ask a human to vet each operation. This is of course infeasible, as Chinese webnovels can have lengths well into thousands of chapters, with hundreds of labels per chapter. Even a small fraction of this number can be extrememly costly to vet for an experienced Chinese reader, let alone a human who barely knows any Chinese. An alternative solution is to force a human to approve a 'type' of operation on a specific input. For example, in the merging process, we may have a situation where two characters' names show up side-by-side and the NER program labels both characters' names individually at times, along with the combined name. To be specific, we may catch the following patterns:

- `a`
- `b`
- `ab`
- `a` `b`

Here "a" and "b" are substitutes for words. The merge function can then flag `a` `b` to be merged, or `ab` to be split. We can call the first operation `merge(a,b)` and the second `split(ab, a)`. It may be likely that only one (or none) of these operations is correct for most of these occurences (verification needed). As such, if there is a way to justify that this is the case, then this significantly reduces the review time.

In fact, the author has come across this specifc issue more than once before. This of course extends to other filter functions, so it is important to find an efficient and potentially automated solution to this problem.

One final issue is the lack of ability to edit already translated chapters to suit the reader's taste.

All the issues described above cannot be resolved without some sort of human intervention (or they can, but at the cost of labeling and translation quality). As such, these issues are best resolved on the frontend, as opposed to the backend.

## Proposed Solutions

We will start by addressing step 2 first, as that is the first step that requires manual review. At a high level, there are four core operations that this filtering operation must be able to perform:

1. Flag instances as candidates for filtering. We will denote this function by `flag_instances() -> list[Instance]`. An instance here is just the type that we pass into the next step. For example, if our filter was to flag by score (i.e. all labels below a minimum score threshold), then an instance could just be a `Label`. If our filter was to merge adjacent labels, then an instance could be a pair `(Label, Label)` (or maybe more sophisticatedly, a `list[Label]` if there are multiple adjacent labels in a row).
2. Retrieve the context around a given instance. This could be the sentence , the paragraph, or even the chapter around a label (or whatever else you want). We will denote this function by `get_context(Instance) -> Context`.
3. Provide an automated framework to decide whether a given instance should actually have the filter operation performed. This could be through manual review, or be automated. We will denote this function by `decide_instance(Instance, Context, ...)`. We keep additional parameters for things like human approval, etc. that cannot be obtained through just an instance and context.
4. Decide whether to perform filtering, and perform the filter operation on all flagged instances. We will denote this function `apply_filter(list[Instance])`.

This is a rather high level of abstraction, with relatively few details. Firstly, one version of `flag_instance` for one specific filter function may not be compatible with a version of `get_context`, as the `Instance` types are not the same between them. Hence it is important to specify the callable `get_context` functions from a `flag_instance` function.

To model this, we will create a `Filter<Instance, Context>` class using generic types `Instance` and `Context`. A `Filter<Instance, Context>` object will have the following methods/attributes:
1. `flag_instances() -> list[Instance]`
2. A list of functions `get_context_list: list[Callable[[Instance], Context]]`. Note that the callables themselves can be defined outside the class to save memory. 
3. A list of functions `decide_instance_list : list[Callable[[Instance, Context, ...], bool]]`. Same note as (2).
4. A function `apply_filter(list[Instance])`. This performs the actual filtering.

These functions will be defined on the backend, with a communication protocol to the frontend. The frontend will store manage all the state associated with the operation. Furthermore, `apply_filter` should be called using information sent from the frontend. This is feasible as the `Instance` data structure is designed to be small, and the frontend should not store a significant number of `Context` objects at a time.

One method for the frontend to use this abstraction is as follows:

1. Group the return of `filter.flag_instances()` by `Instance` value. For example, for a `merge_filter : Filter<Tuple[Label, Label], str>` object, where `merge_filter.flag_instances()` returns a list containing some instances `("张三", "丰")`, these instances should all be grouped.
2. For each group, sample a subset of the group at random (say of size O(log n)) and compute for each instance `instance` in the subset, select a `get_context` in `filter.get_context_list` and a  `decide_instance` in `filter.decide_instance_list` and compute `context = get_context(instance)`, `decision = decide_instance(instance, context)`. The results of each intermediary step should be shown to the user.
3. Based on the output of the `decision` variables, the user should be allowed to accept or reject this group of instances. The exact details of this step are implementation-specific and will be determined in a later section.

The implementations of `filter.flag_instances` and each of the `get_context` functions should be fast and straightforward. There is possibility to make these batchable to increase throughput. For the `decide_instance` functions, one example might be to pass the context and instance to an LLM and have it return `yes` or `no`. Another implementation might be to send human approval or not.

We can use the same ideas as step 2 for steps 4/7. The key idea is once again to get context around a specific label. We can then add a frontend side functionality to view the context around a label, along with the ability to pass this context to an LLM to assist with decision making.

## UI Requirements

Drafted with the help of Claude.

### Overview

The edit novel page serves as the primary workspace for the translation pipeline. Rather than a single monolithic page, we design around composable components that can be arranged in different layouts.

### Core Components

#### Chapter Viewer

A component for displaying a single chapter's content with inline label visualization.

**Subcomponents:**

*Label Group Selector*

- Dropdown or sidebar listing all label groups for the current novel
- Shows: group name, owner, label count
- Toggle visibility per group (show/hide that group's labels)
- Active group highlighted (the one being edited)
- "Create new group" option

*Text Display*

- Chapter text rendered with labels as colored spans
- Each label group gets a distinct color (user-configurable?)
- Label visualization:
    - The labeled word is highlighted with background color
    - Draggable handles at start/end positions for resizing
    - The label itself (the colored span) is draggable to move the entire label
- Overlapping labels from different groups shown with layered/striped coloring

**Properties:**
- `revision_id` — which content to display
- `active_label_group_id` - which group is being edited (others are view-only)
- `visible_label_groups: string[]` - which groups to render
- `editable: boolean` - whether labels can be modified
- `on_label_change: (label) => void` - callback when a label is moved/resized

**Interactions:**

- Drag label endpoints -> resize label (adjust label_start / label_end)
- Drag label body -> move label to new position
- Click label -> show popover with details (entity group, score, actions: edit, delete)
- Double-click text -> create new label (select start/end)
- Hover -> subtle highlight + tooltip

**Scroll sync:**

- Exposes scrollTo(position) method for external control
- Emits onScroll(position) for sync with other viewers

#### Chapter Navigator

A sidebar or panel for navigating between chapters.

**Display:**

- Dropdown list of chapters (by chapter number)
- Previous and next button
- By default, goes to the primary revision, or if that does not exist, the most recent revision
- Indicators for: has labels, has revisions, translation status
- Current chapter highlighted

**Interactions:**

- Click to load chapter in viewer

#### Dual Chapter View

A layout component that renders two ChapterViewer instances side by side.

**Properties:**

- `left_revision_id`, `right_revision_id` - the two chapters/revisions to display
- `sync_scroll`: boolean - whether scrolling is synchronized
- Sync scrolling approach (TBD):

*Options:*
- Option A: Pixel-based - scroll positions match exactly
- Option B: Paragraph-based - align by paragraph index (better for different-length translations)
- Option C: Label-based - align by label positions (most precise but complex)
For now, Option A is simplest to implement. Option B is likely the sweet spot.

#### Filter Workflow Panel
The UI for running and reviewing filter operations (as described in Proposed Solutions).

**Display:**

- Filter selector (dropdown or list)
- Groups table: instance value, count, sample decisions, status
- Expandable rows showing sampled contexts and decisions

**Interactions:**

- Run filter -> populates groups
- Expand group -> fetch/display sampled contexts
- Approve/reject group
- Apply approved filters

#### Label Sidebar
A panel showing all labels in the current chapter (or across chapters).

**Display:**

- List of labels, sortable by: position, entity group, score
- Filter by entity group
- Search by word

**Interactions:**

- Click label -> scroll chapter viewer to that position
- Edit label inline (word, entity group)
- Delete label

#### Glossary Panel

Aggregated view of unique terms across the novel (step 3 in pipeline).

**Display:**

- Table: term, entity group, occurrence count, translation (if exists)
- Sortable and filterable

**Interactions:**

- Click term -> show all contexts (across chapters)
- Jump to shown context on click
- Edit translation
- Mark as reviewed/verified