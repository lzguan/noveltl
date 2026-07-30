# Requirements

This document details the requirements that we set for the filters feature.

## Core capabilities:

- User should be able to create new functions and upload them to database inside a GUI editor by combining the building blocks in `functions.py`. User should be able to search for functions from a search bar or dropdown. 
- User should be able to use any given runner and query any function to use in the runner. When being asked for id parameters, user should be given a dropdown to view the possible options directly.
- User should be able to load a workflow for viewing.
- User should be able to specify any subset of groupings on a workflow and for each grouping, receive a list of possible values in that grouping. Group values should be displayed in a searchable dropdown, so for `n` groups there should be `n` dropdowns. Users should be able to select any number of values from each dropdown. Groupings should be selectable from a dropdown.
- After selecting the subset of groupings on the workflow and selecting a list of values from each grouping, user should be given the list of instances with the corresponding values on these groupings in tabular format, where the columns are the field and the rows are the instance values. Individual cells should be one of (string/float/int/bool/labelref/textspan) objects, where string/float/int/bool values are displayed as-is, textspans and labelrefs are double-clickable and will cause the user to open the corresponding chapter and highlight the corresponding text. Labelrefs should come with a little information icon that displays the full label on click. Double clicking a labelref should also switch the active label group to the corresponding one. 
- All data-heavy displays (dropdowns, tables, etc.) should be paginated.

## Illustrative UI

These wireframes illustrate the required information and interactions. They do
not prescribe the final layout or visual styling.

### Function library and editor

```text
+----------------------------------------------------------------------------------+
| Functions                                      [ Search functions... ] [ + New ] |
+---------------------------+------------------------------------------------------+
| project.low_score         | Name       [ low_score                            ]  |
| project.label_word        | Namespace  [ project                              ]  |
| shared.has_text           |                                                      |
|                           | Input schema                  Output                   |
| Page 1 of 4   [<] [>]     | { label: LabelRef }           Bool                    |
+---------------------------+------------------------------------------------------+
| Building blocks           | Function                                              |
| [ Search blocks... ]      |                                                      |
|                           | Call                                                  |
| Comparison                | +-- function: Compare(float, less than)               |
|   Compare                 | +-- argument 1                                        |
| Logic                     | |   `-- Call                                          |
|   And                     | |       +-- function: ScoreOf                         |
|   Or                      | |       `-- argument: Get("label")                    |
|   If                      | `-- argument 2: LiteralFloat(0.60)                    |
| Labels and text           |                                                      |
|   WordOf                  | [ Validate ]                         [ Save function ] |
|   ProjectToSpan           | Validation: compatible { label: LabelRef } -> Bool    |
+---------------------------+------------------------------------------------------+
```

The function search searches saved function definitions. The building-block
search searches the closed set of nodes supported by the backend. The editor
must display validation errors at the node that caused them and must not allow
an invalid definition to be saved.

### Runner execution

```text
+--------------------------------------------------------------------------+
| Run operation                                                            |
+--------------------------------------------------------------------------+
| Runner             [ Map                                             v ] |
| Source workflow    [ Autolabel cleanup / low-score labels            v ] |
| Function           [ project.label_word                              v ] |
| Output name        [ Labels with derived word                         ] |
|                                                                          |
| Source schema                      Result schema                          |
| { label: LabelRef }                { label: LabelRef, word: String }      |
|                                                                          |
| Function list: compatible functions only                                 |
| ID fields: searchable, paginated resource selectors                      |
|                                                                          |
|                                                        [ Run operation ] |
+--------------------------------------------------------------------------+
| Status: processing                                                       |
| Working...                                                               |
| The workflow remains viewable while the operation is running.            |
+--------------------------------------------------------------------------+
```

The form changes with the selected runner and exposes its required resource
IDs and function parameters. Selectors show human-readable names in addition
to IDs. Processing and failure states must remain visible after navigation or
page reload.

### Workflow and grouped instances

```text
+----------------------------------------------------------------------------------+
| Autolabel cleanup                                      complete     [ Run action ] |
| 12,481 instances  |  Schema: label, word, score                                |
+----------------------------------------------------------------------------------+
| Groupings                                                                       |
| [ + Add grouping: select... v ]                                                 |
|                                                                                  |
| Normalized word                                                                 |
| [ Search values...                         ]  Selected: [青石城 x] [林凡 x]       |
|  [ ] 玄天宗 (184)   [x] 青石城 (73)   [x] 林凡 (51)   Page 1 of 28  [<] [>]     |
|                                                                                  |
| Entity group                                                                    |
| [ Search values...                         ]  Selected: [PERSON x]               |
|  [x] PERSON (932)  [ ] LOCATION (410)  [ ] ORGANIZATION (205)  [<] [>]          |
+----------------------------------------------------------------------------------+
| Instances                                                      [ Clear filters ] |
+------+----------------------------+------------------+---------+------------------+
|  #   | label                      | word             | score   | accepted         |
+------+----------------------------+------------------+---------+------------------+
|  1   | 林凡  [i]                  | 林凡             | 0.42    | true             |
|  2   | 青石城 [i]                 | 青石城           | 0.38    | false            |
|  3   | 玄天宗 [i]                 | 玄天宗           | 0.55    | true             |
+------+----------------------------+------------------+---------+------------------+
| Rows 1-50 of 124                              [ 50 per page v ]  [<] 1 2 3 [>]    |
+----------------------------------------------------------------------------------+

Label information
+--------------------------------------+
| 林凡                                 |
| Group: Characters                    |
| Entity: PERSON       Score: 0.42     |
| Chapter 17 · content version 3       |
| Offsets 128-130                      |
|                         [ Open label ]|
+--------------------------------------+
```

Clicking the information icon opens the label details without navigating away.
Double-clicking a `LabelRef` or `TextSpan` opens the referenced chapter and
highlights its range. A `LabelRef` additionally activates its label group
before focusing the label.
