# Memory UI overview

This document describes the intended high-level structure of the memory panel.
The wireframes illustrate information hierarchy and behavior rather than final
spacing or visual styling.

## Navigation hierarchy

The memory group is selected first. The next layer selects the plugin or view,
which then owns the controls and layout below it.

```text
Memory group selector
|
+-- Plugin selector
    |
    +-- View all memories
    |   +-- From all chapters
    |   +-- Memory type filter
    |   `-- Paginated memory list
    |
    `-- Glossary
        +-- Term search
        +-- Show all terms
        `-- Paginated term accordion
            +-- Add memory for a term
            `-- Paginated associated-memory list
```

## Shared panel header

The memory group selector appears at the top of the panel. The plugin selector
appears directly below it. Context controls belong to the selected view rather
than applying globally.

```text
+------------------------------------------------------+
| Memory group                                        |
| [ Main glossary                              v ] [+] |
+------------------------------------------------------+
| Plugin                                               |
| [ View all memories v ]                              |
+------------------------------------------------------+
|                                                      |
|                 Selected view                        |
|                                                      |
+------------------------------------------------------+
```

The plugin options are `View all memories` and `Glossary`. Future memory plugins
may add other options.

## View all memories

This view displays memories directly. It defaults to memories active in the
currently open chapter.

```text
+------------------------------------------------------+
| Plugin                                               |
| [ View all memories v ]                              |
+------------------------------------------------------+
| [ ] From all chapters       Type [ All types      v] |
+------------------------------------------------------+
| pending  fact                         Ch. 12+ · agent |
| Lin Fan is the sect's newest inner disciple.         |
+------------------------------------------------------+
| approved  relation                    Ch. 8+ · user  |
| Lin Fan is the disciple of Elder Mo.                 |
+------------------------------------------------------+
| [ Previous ]                 1-20 of 86      [ Next ] |
+------------------------------------------------------+
```

### Scope

`From all chapters` is off by default.

- Off: show memories active in the currently open chapter.
- On: show memories from every chapter, including memories that are no longer
  active.

Both scopes use a paginated query and list. Selecting a different page should
not require loading the entire result set.

### Memory type filter

A compact selector filters the current list by memory type. The filter applies
in both chapter-context and all-chapters scopes.

## Glossary

The Glossary view presents terms as a searchable, paginated accordion.

```text
+------------------------------------------------------+
| Plugin                                               |
| [ Glossary v ]                                       |
+------------------------------------------------------+
| Search terms                                         |
| [ Lin Fan________________________________________ ]  |
| [ ] Show all terms                      [+ New term]  |
+------------------------------------------------------+
| > 林凡                         14 memories  [+ Memory] |
+------------------------------------------------------+
| v 林家                          8 memories  [+ Memory] |
| +--------------------------------------------------+ |
| | pending  fact                      Ch. 3+ · agent | |
| | Content                         | Associated terms | |
| | The Lin clan is based in        | 林家              | |
| | Qingyang.                       | 青阳镇            | |
| +--------------------------------------------------+ |
| | approved  event                    Ch. 19 · user  | |
| | Content                         | Associated terms | |
| | The Lin clan tournament begins. | 林家              | |
| +--------------------------------------------------+ |
| | [ Previous ]          1-10 of 23         [ Next ] | |
| +--------------------------------------------------+ |
+------------------------------------------------------+
| > 林动                         6 memories  [+ Memory] |
+------------------------------------------------------+
| [ Previous ]                 1-20 of 54      [ Next ] |
+------------------------------------------------------+
```

### Term scope and search

`Show all terms` is off by default.

- Off: show terms associated with memories active in the currently open
  chapter.
- On: show every term in the selected memory group.

The term search filters within the selected scope. Search results remain
paginated.

### Term ordering

Terms are sorted by their number of associated memories by default, with terms
having more associated memories appearing first. The displayed count and sort
order should use the currently selected scope. Ties may be sorted
alphabetically.

### Term accordion

Each term row displays its associated-memory count and an `Add memory` action.
Expanding a row loads a separately paginated list of memories associated with
that term.

Each memory uses the same basic presentation and actions as the all-memories
list. Its associated glossary terms appear to the right of the memory content.
The nested list respects `Show all terms`: when the switch is off it contains
only memories active in the current chapter, and when it is on it contains all
memories associated with the term.

## Adding a glossary memory

Selecting `Add memory` beside a term opens the memory form with that term
selected by default. The user may search for and select additional terms, or
remove selected terms before submitting.

```text
+------------------------------------------------------+
| New glossary memory                              [x] |
+------------------------------------------------------+
| Content                                              |
| +--------------------------------------------------+ |
| |                                                  | |
| +--------------------------------------------------+ |
|                                                      |
| Type [ Fact v ]              Scope [ Automatic v ]  |
|                                                      |
| Terms                                               |
| [ 林家 x ] [ Search for another term...__________ ] |
|   +----------------------------------------------+   |
|   | 林凡                                         |   |
|   | 青阳镇                                       |   |
|   `----------------------------------------------'   |
|                                                      |
|                              [ Cancel ] [ Create ]   |
+------------------------------------------------------+
```

The term selector is a searchable multi-select. A memory may be associated with
multiple terms.

## Pagination summary

Pagination is independent at each list boundary:

- The active-chapter memory list.
- The all-chapters memory list.
- The glossary term list.
- The associated-memory list inside each expanded term.

Changing scope, search, or memory type returns the corresponding list to its
first page.
