---
name: rename-refactor
description: Systematic multi-layer rename/refactor across the full stack. Use when renaming models, fields, functions, or tables and need to propagate changes through all layers (models → permissions → schemas → exceptions → service → router → tests → docs → frontend).
---

# Rename Refactor Skill

Systematically propagate a rename or model refactor across all layers of the NovelTL stack. Each layer is checked in dependency order so downstream layers are updated after upstream layers are correct.

## Inputs

Before starting, confirm the following with the user (or extract from their request):

1. **What is being renamed?** (model, field, function, table, exception, etc.)
2. **Old name → New name** (e.g., `Revision` → removed, `RevisionText` → `ChapterContent`)
3. **Scope** — which layers to update (default: all)
4. **Is this a rename, a removal, or a structural change?** (e.g., collapsing two models into one)

## Layer Order

Process layers in this exact order. For each layer, search for all occurrences of the old name, update them, and verify consistency before moving to the next layer.

### Layer 1: Database Models (`backend/src/{service}/models.py`)
- Rename class, `__tablename__`, columns, relationships, constraints, FK references
- Update `TYPE_CHECKING` imports in other models that reference this model
- Check `backend/src/models.py` for the wildcard import

### Layer 2: Constants (`backend/src/{service}/constants.py`)
- Rename any enum values, max length constants, or other constants tied to the old name

### Layer 3: Permissions (`backend/src/{service}/permissions.py`)
- Rename permission helper functions: `{old}_mod_access_{op}` → `{new}_mod_access_{op}`
- Update internal references to renamed models/columns
- Update imports in other services' permissions files that reference these helpers

### Layer 4: Schemas (`backend/src/{service}/schemas.py`)
- Rename Pydantic model classes and their fields
- Update field names to match new column names
- Check `model_validate` and `from_attributes` usage in service/router layers

### Layer 5: Exceptions (`backend/src/{service}/exceptions.py`)
- Rename exception classes (e.g., `RevisionNotFoundException` → `ChapterContentNotFoundException`)
- Check base class inheritance is preserved

### Layer 6: Service (`backend/src/{service}/service.py`)
- Rename functions: `query_revision_*` → `query_chapter_content_*`, etc.
- Update all model references, permission helper calls, schema references
- Update docstrings (Args, Returns, Raises sections)
- Update error handling (exception names in catch blocks)

### Layer 7: Router (`backend/src/{service}/router.py`)
- Update imports (service functions, schemas, exceptions)
- Rename endpoint functions
- Update URL paths if applicable
- Update response_model references
- Update exception handling in try/except blocks
- Update docstrings

### Layer 8: Cross-service references
- Search ALL other services for imports/references to the renamed entity:
  ```
  grep -r "old_name" backend/src/ --include="*.py"
  ```
- Common cross-service references:
  - `labels/service.py` and `labels/permissions.py` reference novel models
  - `autolabels/service.py` and `autolabels/permissions.py` reference novel models
  - `filters/` references label and novel models

### Layer 9: Tests (`backend/tests/`)
- Update model imports in test files
- Update fixture populators in `tests/fixtures/populators/`
- Update function calls to renamed service functions
- Update exception references in test assertions
- Verify fixtures create objects with correct new field names

### Layer 10: Documentation (`docs/`)
- Search all markdown files for old names
- Update architecture diagrams, code examples, table references
- Update the `write-documentation` skill's stale names list
- Update `Last Updated` dates on modified docs

### Layer 11: Frontend types (`frontend/src/types/`)
- Rename TypeScript interfaces/types
- Update field names (remember: frontend uses camelCase)

### Layer 12: Frontend API (`frontend/src/api/`)
- Update API function names and return types
- Update snake_case ↔ camelCase mappers
- Update endpoint URLs if they changed

### Layer 13: Frontend API tests (`frontend/src/api/__test__/`)
- Update mock data to match new response shapes
- Update function names in test calls
- Update type assertions

### Layer 14: Frontend components and pages
- Update imports and usage of renamed types/API functions
- Search for string literals containing old endpoint paths

### Layer 15: Skills (`.claude/skills/`)
- Search all SKILL.md files for old names in code examples, patterns, and checklists
- Update the `write-documentation` skill's stale names list
- Update any test skill patterns that reference old models/schemas

### Layer 16: Agents (`.claude/agents/`)
- Search all agent definition files for old names in context sections
- Update any "current refactor context" or similar embedded knowledge

## Verification

After completing all layers:

1. Run `grep -r "old_name" backend/src/ --include="*.py"` to find any remaining references
2. Run `grep -r "old_name" frontend/src/ --include="*.ts" --include="*.tsx"` for frontend
3. Run `grep -r "old_name" docs/ --include="*.md"` for docs
4. If using agent teams, ask backend-checker and frontend-checker to run type checks

## Tips

- Process one rename at a time. Don't batch multiple renames unless they're tightly coupled.
- When a model is removed (not just renamed), mark functions that depended on it for removal or restructuring rather than blindly renaming.
- When relationships change (e.g., FK path shortens), the joins in service queries need structural changes, not just name swaps.
- Keep a running list of changes made per layer so the team lead can review.
