---
name: impact-analysis
description: Trace all dependents of a changed symbol, file, or model across the full stack. Use when planning a change to understand what will break, or after a change to verify nothing was missed.
---

# Impact Analysis Skill

Trace the blast radius of a change across the full NovelTL stack. Produces a structured report of every file and function that depends on the changed entity.

## Inputs

1. **What changed?** — A model, field, function, permission helper, schema, endpoint, etc.
2. **Where?** — The file and line/symbol name
3. **Type of change** — rename, removal, signature change, structural change

## Analysis Process

### Step 1: Direct dependents

Search for direct imports and references to the changed symbol:

```bash
# Python backend
grep -rn "from.*import.*SymbolName" backend/src/ --include="*.py"
grep -rn "SymbolName" backend/src/ --include="*.py"

# Tests
grep -rn "SymbolName" backend/tests/ --include="*.py"

# Frontend
grep -rn "SymbolName" frontend/src/ --include="*.ts" --include="*.tsx"

# Docs
grep -rn "SymbolName" docs/ --include="*.md"
```

### Step 2: Indirect dependents (for models/permissions)

If the changed entity is a **model or permission helper**, trace the dependency chain:

1. **Model** → which permission helpers reference it? → which service functions use those helpers? → which router functions call those services? → which tests exercise those routes?
2. **Permission helper** → which service functions call it? → which routers depend on those services?
3. **Schema** → which routers use it as request/response model? → which frontend API functions map it?

Use the LSP tool for precise tracing:
- `findReferences` on the symbol
- `incomingCalls` to trace call hierarchy
- `goToDefinition` to verify the source

### Step 3: Cross-service dependencies

Check these known cross-service reference patterns:
- `labels/` imports from `novels/models.py` and `novels/permissions.py`
- `autolabels/` imports from `novels/models.py` and `novels/permissions.py`
- `filters/` imports from `labels/` and `novels/`
- `autolabels/worker/` imports from `autolabels/models.py` and `novels/models.py`
- Frontend `api/` files map to backend router endpoints
- Test fixtures in `tests/fixtures/populators/` construct model instances directly

### Step 4: FK and join path analysis (for model changes)

If a model or FK relationship changed:
1. Find all SQLAlchemy `.join()` calls that reference the old model
2. Find all `.where()` clauses that reference columns on the old model
3. Find all `relationship()` back_populates that reference the old model
4. Check alembic migrations for FK constraint names that may need updating

### Step 5: Compile report

Output a structured report:

```
## Impact Analysis: [SymbolName]

### Direct dependents (imports/references)
| File | Line | Usage |
|------|------|-------|
| ... | ... | ... |

### Indirect dependents (via call chain)
| File | Function | Depends via |
|------|----------|-------------|
| ... | ... | calls X which uses Y |

### Test coverage
| Test file | What it tests | Will break? |
|-----------|---------------|-------------|
| ... | ... | Yes/No/Maybe |

### Frontend impact
| File | Function/Component | Impact |
|------|-------------------|--------|
| ... | ... | ... |

### Documentation references
| Doc file | Line | Context |
|----------|------|---------|
| ... | ... | ... |

### Recommended update order
1. ...
2. ...
```

## Tips

- For field renames, search for both `old_field_name` and the camelCase equivalent (`oldFieldName`) to catch frontend references.
- For model removals, check if any test fixtures directly instantiate the model.
- The report should distinguish between "will definitely break" vs "might need updating" — e.g., a docstring mention is lower priority than a runtime import.
