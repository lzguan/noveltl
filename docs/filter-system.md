# Filter System

**Last Updated**: March 5, 2026  
**Status**: Complete

This document describes the Filter abstraction - a four-phase pipeline for processing and filtering labels with LLM-assisted decision-making.

## Overview

The Filter system provides a generic framework for manipulating labels at scale. It addresses a key challenge: **filtering thousands of labels across hundreds of chapters while keeping humans in the loop**.

### The Problem

When autolabeling novels with NER models:
- False positives are common (e.g., common words misidentified as names)
- Ambiguous cases require context to verify (e.g., "Washington" could be a person or place)
- Manual review of every label is infeasible (100+ chapters × 200 labels = 20,000+ reviews)
- Bulk operations (merge/split) can introduce errors at scale

### The Solution

A four-phase pipeline that allows:
1. **Filtering at scale** - Process thousands of labels efficiently
2. **Sampling for review** - Show user representative examples instead of all instances
3. **Automated decisions** -  LLM-assisted or rule-based filtering
4. **Partial application** - Apply filter to approved instances only

## Four-Phase Pipeline

Every filter implements these phases:

```
┌────────────────┐         ┌─────────────────┐
│ 1. Flag        │────────▶│  2. Get Context │
│ Find candidates│         │  Fetch surrounding  │
└────────────────┘         │  text/metadata  │
                           └────────┬────────┘
                                    │
        ┌───────────────────────────┘
        │
        ▼
┌────────────────┐         ┌─────────────────┐
│ 3. Decide      │────────▶│  4. Apply       │
│ Auto or manual │         │  Execute changes│
│ approval       │         │  to database    │
└────────────────┘         └─────────────────┘
```

### Phase 1: Flag Instances

**Purpose:** Identify candidate labels for filtering

**Example (ScoreFilter):**
```python
def flag_instances(db, user, options: ScoreFlagOptions) -> list[SingleLabel]:
    # Find all labels with score < options.min_score
    # in label group options.label_group_id
    # for chapters options.start to options.end
    return flagged_labels
```

**Characteristics:**
- Fast database query (indexed)
- Returns list of "instances" (type varies by filter)
- Instance types:
  - ScoreFilter: `SingleLabel` (one label)
  - MergeFilter: `Tuple[Label, Label]` (adjacent pair)
  - SplitFilter: `Label` (potentially composite)

### Phase 2: Get Contexts

**Purpose:** Retrieve surrounding text/metadata for each instance

**Example (ScoreFilter):**
```python
def get_contexts(db, user, instances, options: ScoreGetContextOptions) -> list[SentenceContext]:
    # For each label, find the sentence it appears in
    # using options.delimiters to detect sentence boundaries
    return contexts
```

**Characteristics:**
- Batched database queries (efficient joins)
- Returns context object per instance (or None if unavailable)
- Context types:
  - `SentenceContext`: Sentence text + label position
  - `ParagraphContext`: Paragraph text
  - `AdjacentLabelsContext`: Nearby labels

### Phase 3: Decide Instances

**Purpose:** Determine which instances should be filtered

**Example (ScoreFilter auto mode):**
```python
def decide_instances(db, user, instance_contexts, options: ScoreDecideOptions) -> list[bool]:
    # For each (instance, context) pair:
    # If any options.exclude_phrases appear in context text, return False
    # Otherwise return True
    decisions = []
    for instance, context in instance_contexts:
        if any(phrase in context.text for phrase in options.exclude_phrases):
            decisions.append(False)  # Don't filter this one
        else:
            decisions.append(True)   # Filter it
    return decisions
```

**Modes:**
- **Auto** - Rule-based or LLM-assisted decisions
- **Manual** - User provides decisions via frontend

**Future LLM Integration:**
```python
async def decide_with_llm(instance, context, llm_params):
    prompt = f"Is '{instance.word}' a valid {instance.entity_type}? Context: {context.text}"
    response = await llm.ask(prompt)
    return response.lower() == "yes"
```

### Phase 4: Apply Filter

**Purpose:** Execute the actual database modifications

**Example (ScoreFilter):**
```python
def apply_filter(db, user, label_group_id, instances, options: ScoreApplyOptions):
    # Delete all labels in instances list
    label_ids = [inst.label_id for inst in instances]
    db.execute(delete(Label).where(Label.label_id.in_(label_ids)))
    db.commit()
```

**Characteristics:**
- Atomic transaction (all or nothing)
- Permission checks (user must have edit access to label group)
- Accepts explicit instance list (partial application supported)

## Filter Abstraction

### Generic Type Signature

```python
Filter[
    FlagInstancesOptions,     # Phase 1 options schema
    GetContextsOptions,       # Phase 2 options schema
    DecideInstancesOptions,   # Phase 3 options schema
    ApplyFilterOptions,       # Phase 4 options schema
    Instance,                 # Instance data type
    Context                   # Context data type
]
```

### Protocol Definition

From `backend/src/filters/filter_base.py`:

```python
class Filter(Protocol):
    description: str
    supports_decide: bool     # Some filters may skip decide phase
    supports_apply: bool      # Some filters may be read-only
    
    # Schema types for OpenAPI generation
    instance_schema: type[InstanceBase]
    context_schema: type[ContextBase]
    flag_instances_options_schema: type[FlagInstancesOptionsBase]
    get_contexts_options_schema: type[GetContextsOptionsBase]
    decide_instances_options_schema: type[DecideInstancesOptionsBase]
    apply_filter_options_schema: type[ApplyFilterOptionsBase]
    
    def flag_instances(self, db, current_user, options) -> list[Instance]: ...
    def get_contexts(self, db, current_user, instances, options) -> list[Context | None]: ...
    def decide_instances(self, db, current_user, instance_contexts, options) -> list[bool]: ...
    def apply_filter(self, db, current_user, label_group_id, instances, options) -> None: ...
```

## Implemented Filters

### ScoreFilter

**Purpose:** Remove low-confidence labels

**Instance:** `SingleLabel` (label ID + basic metadata)

**Context:** `SentenceContext` (sentence text + label position)

**Phases:**
1. **Flag:** Labels with `score < min_score`
2. **Context:** Find sentence around each label using configurable delimiters
3. **Decide:** 
   - Auto mode: Exclude if context contains blacklisted phrases
   - Manual mode: User reviews each with context
4. **Apply:** Delete approved labels

**Use Cases:**
- Remove obvious NER errors (score < 0.5)
- Filter out common words misidentified as names
- Clean up labels before manual review

**Configuration:**
```json
{
  "flag": {
    "label_group_id": 42,
    "min_score": 0.85,
    "start": 0,
    "end": 100,
    "flag_dirty": false
  },
  "context": {
    "delimiters": ".!?。！？\n",
    "refresh": false
  },
  "decide": {
    "mode": "auto",
    "exclude_phrases": ["他", "她", "的", "说"]
  }
}
```

## Planned Filters

### MergeFilter

**Purpose:** Combine adjacent labels into single label

**Instance:** `Tuple[Label, Label]` - Adjacent label pairs

**Context:** Text between labels

**Example:**
```
Labels: ["张" (PER), "三" (PER)] → Merge to "张三" (PER)
```

**Challenges:**
- Chinese has no spaces - harder to detect boundaries
- Risk of merging unrelated entities ("George" + "Washington" could be two people or one)
- Solution: Show context, let user/LLM decide

### SplitFilter

**Purpose:** Break composite label into components

**Instance:** `Label` - Label potentially containing multiple entities

**Context:** Surrounding labels, sentence structure

**Example:**
```
Label: "George Washington" → Split to ["George", "Washington"]
```

**Use Cases:**
- NER model incorrectly merged two names
- Phrase contains multiple entity types

### DeduplicationFilter

**Purpose:** Remove duplicate labels across chapters

**Instance:** `list[Label]` - All instances of same word

**Context:** Aggregated statistics (frequency, chapters)

**Use Cases:**
- One character name labeled 100 times, only need one instance for glossary
- Remove redundant labels to reduce review burden

## API Design

### Endpoints

```
GET    /filters/                          # List available filters
GET    /filters/{filter_name}             # Get filter metadata
GET    /filters/{filter_name}/schema      # Get OpenAPI schemas for all phases
POST   /filters/{filter_name}/flag        # Phase 1: Flag instances
POST   /filters/{filter_name}/context     # Phase 2: Get contexts
POST   /filters/{filter_name}/decide      # Phase 3: Decide instances
POST   /filters/{filter_name}/apply       # Phase 4: Apply filter
```

### Example Flow

**1. Flag instances:**
```http
POST /filters/score_filter/flag
{
  "label_group_id": 42,
  "min_score": 0.85
}

Response: 200 OK
{
  "instances": [
    {"label_id": 100, "word": "他", "score": 0.6},
    {"label_id": 150, "word": "的", "score": 0.7}
  ]
}
```

**2. Get contexts:**
```http
POST /filters/score_filter/context
{
  "instances": [
    {"label_id": 100, "word": "他", "score": 0.6}
  ],
  "delimiters": "。！？"
}

Response: 200 OK
{
  "contexts": [
    {
      "label_id": 100,
      "text": "他说：「你好吗？」",
      "label_start_in_context": 0
    }
  ]
}
```

**3. Decide (manual):**
```http
POST /filters/score_filter/decide
{
  "instance_contexts": [
    {
      "instance": {"label_id": 100},
      "context": {"text": "他说：「你好吗？」"}
    }
  ],
  "mode": "manual",
  "decisions": [true]  // User approved filtering
}

Response: 200 OK
{
  "decisions": [true]
}
```

**4. Apply:**
```http
POST /filters/score_filter/apply
{
  "label_group_id": 42,
  "instances": [
    {"label_id": 100, "word": "他", "score": 0.6}
  ]
}

Response: 200 OK
{
  "status": "success",
  "filtered_count": 1
}
```

## Frontend Integration

### UI Workflow

1. **User selects filter** from dropdown
2. **Configure options** - Set min_score, chapter range, etc.
3. **Preview instances** - Show sample flagged labels with contexts
4. **Review decisions** - Approve/reject in batches or individually
5. **Apply filter** - Execute changes to database

### Sampling Strategy

Instead of showing all 10,000 flagged labels:

1. **Group by instance value** - e.g., all instances of "他"
2. **Sample O(log n)** - Show ~10 representative examples per group
3. **User reviews samples** - If all samples look correct, assume group is correct
4. **Apply to all** - Filter entire group, not just samples

### State Management

Frontend tracks:
- Current filter and phase
- Flagged instances (paginated)
- User decisions per instance/group
- Applied vs. pending filters

## Schema Communication

### OpenAPI Integration

Filters expose Pydantic schemas that automatically generate OpenAPI specs:

```python
class ScoreFlagInstancesOptions(FlagInstancesOptionsBase):
    type: Literal["score_filter_flag_instance_options"]
    label_group_id: int = Field(..., description="...")
    min_score: float = Field(..., ge=0.0, le=1.0, description="...")
```

Frontend can:
- Fetch schema via `GET /filters/{name}/schema`
- Render dynamic forms from schema
- Validate input client-side

### Type Discriminator

Each schema has a `type` field for runtime type checking:

```python
type: Literal["score_filter_flag_instance_options"]
```

This solves type erasure at REST API boundary.

## Performance Considerations (AI estimations, verify)

### Flag Phase

- **Typical:** 50ms for 10K labels (indexed query)
- **Optimization:** Add indexes on score, entity_group

### Context Phase

- **Typical:** 200ms for 100 instances (joined query)
- **Optimization:** Batch queries, cache chapter text per request

### Decide Phase

- **Typical:** 10ms for rule-based, 2-5s for LLM per instance
- **Optimization:** Batch LLM requests, parallel API calls

### Apply Phase

- **Typical:** 100ms for 100 deletions (batched DELETE)
- **Optimization:** Use `DELETE IN (...)` instead of loop

## Design Rationale

### Why Four Phases?

Separation of concerns:
- **Flag** is fast, database-focused
- **Context** is I/O-bound, benefits from batching
- **Decide** may involve external services (LLMs)
- **Apply** is transactional, requires atomicity

### Why Generic Types?

Different filters need different instance structures:
- ScoreFilter: Single label
- MergeFilter: Label pair
- SplitFilter: Label + candidates

Generics provide type safety without code duplication.

### Why Partial Application?

User may want to:
- Review samples and apply to subset
- Merge some groups but not others
- Test filter on small batch first

Passing explicit instance list enables flexibility.

## Relevant Files

- `backend/src/filters/filter_base.py` - Base protocol definition
- `backend/src/filters/score_filter.py` - ScoreFilter implementation
- `backend/src/filters/service.py` - Service layer (routes filter calls)
- `backend/src/filters/router.py` - API endpoints
- `backend/src/filters/types.py` - Type definitions and filter registry
- `backend/src/filters/schemas.py` - Pydantic schema base classes
- `backend/src/filters/utils.py` - Helper functions (find_sentence, etc.)
- `tests/filters/` - Filter tests

## See Also

- [architecture.md](architecture.md) - Filter service overview
- [database-schema.md](database-schema.md) - Label table constraints
- [api-design.md](api-design.md) - Filter API endpoint patterns
- [ui-requirements.md](ui-requirements.md) - Frontend component specs
- [conventions.md](conventions.md) - Filter naming conventions
- [requirements.md](requirements.md) - Original motivation for this architecture