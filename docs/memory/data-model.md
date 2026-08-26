# Memory data model

## `memories`

Memories are grouped into memory groups, which are stored in the `memory_groups` table.

Generally speaking, a request to get relevant memories will occur within some context, which we detail a tuple consisting of the chapter id and memory group id. We hence need to quantify exactly what it means when we say memory A is accessible within a given context.

- `memory_id`
- `memory_group_id`
- `memory_type` - what is this memory describing (e.g. event, relation between terms, etc.)
- `memory_observed_in` - which chapter content the memory was recorded on. Purely for tracking purposes.
- `memory_start_num` - the first chapter (inclusive) this memory should be available to access. Cannot be null.
- `memory_end_num` - the last chapter (exclusive) this memory should be available to access. If null, then this memory has no point at which it becomes invalid.
- `supersedes_memory_id` - if memory A corrects/updates information in memory B, then we should have A.supersedes_memory_id = B.memory_id.
- `memory_content` - Self-explanatory.
- `memory_review_status` - Convenience to approve or deny memories.
- `creator_type` - Who created this memory (currently relevant options are USER and AGENT).
- `plugin_name` - Will be explained later.

As you may have guessed, we say a memory is accessible within a context if its memory group id matches the context's memory group id and the context's chapter number lies within the range specified by `memory_start_num` and `memory_end_num`.

## Plugins

Memories are typically not recorded in a vacuum - when recording a memory, there is generally a specific domain associated with that memory. For example, recording a memory could be to remember the definition of a term, something that happened to a character, a significant event in the novel, etc.

Depending on the domain, memories should be recorded at different times. For example, we should record the start of a new arc a lot less often than we should record the actions of our main character. For each of these different possibilities, we should specify rules for when to record such a thing. 

The way we accomplish this is through an auxiliary interface that we call a plugin. Very abstractly, a plugin provides an external data model that is linked by some association to the memories of a given novel, as well as a set of tools to modify memory indirectly through this auxiliary tool and some context for when the use of these tools is appropriate. Interaction with the memory data will then take place through a plugin.

```mermaid
flowchart LR
    A[Agent] --> AI[Agent plugin interface]
    U[User] --> UI[User plugin interface]
    AI --> T[Plugin toolset]
    UI --> T
    T -->|reads and writes| M[(Memory model)]
    T -->|reads and writes| P[(Plugin data model)]
```

This is quite abstract, so we should give an example of a specific plugin.

## Glossary

Some memories are recorded for the explicit purpose of being associated with a character. This plugin gives us the tools to do so.

### Data model

The glossary plugin introduces two tables. The `glossaries` table stores terms
that appear in the source text:

- `term_id`
- `term`
- `memory_group_id`
- `review_status`

A term is unique within its memory group. The same text may still be recorded
in different memory groups, since those groups may serve different languages
or translation workflows.

The `glossary_associations` table links terms to memories:

- `term_id`
- `memory_id`

Together, these columns form the table's primary key. This creates a
many-to-many relationship: one term may accumulate multiple memories over the
course of a novel, and one memory may describe a relationship involving
multiple terms.

```mermaid
erDiagram
    MEMORY_GROUP ||--o{ GLOSSARY_TERM : contains
    MEMORY_GROUP ||--o{ MEMORY : contains
    GLOSSARY_TERM ||--o{ GLOSSARY_ASSOCIATION : has
    MEMORY ||--o{ GLOSSARY_ASSOCIATION : has
```

### User interface

The glossary plugin should provide two complementary ways to inspect its data.
When a chapter is open, users should be able to see the glossary memories that
are active for that chapter alongside the chapter text. A novel-wide glossary
view should let users search terms and inspect the memories associated with
each term across the novel.

Users should also be able to add or rename terms, change the review status of
terms and memories, edit memory content, change the terms associated with a
memory, expire memories, and delete incorrect data. The interface should retain
the distinction between a term and a memory: approving a term does not
implicitly approve every memory associated with it, or vice versa.

### Agent interface

At the beginning of a chapter, the glossary plugin gives the agent the known
glossary terms that occur in that chapter. Memories are retrieved separately
and only when the agent has identified a concrete piece of information that
may duplicate, continue, or supersede existing context.

The plugin exposes four tools to the agent:

- `term_memories` retrieves active memories associated with specified terms.
- `add_term` records a new source-language term.
- `new_memory` records a memory and associates it with one or more terms.
- `supersede_memory` ends an older memory and creates its replacement.

The term itself remains in the source language, while memory content is written
in the language configured by the memory group. The agent processes chapters
in order so memories written for one chapter can become context for later
chapters.
