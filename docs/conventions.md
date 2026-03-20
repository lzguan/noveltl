# Conventions

**Last Updated**: March 19, 2026  
**Status**: Complete

This document defines naming and structural conventions for the NovelTL codebase.

---

## Table of Contents

**[Backend Naming Conventions](#backend-naming-conventions)**

1. [General](#general)
2. [Code Quality Tools](#code-quality-tools)
3. [Database Models](#database-models)
4. [Pydantic Schemas](#pydantic-schemas)
5. [Service Modules](#service-modules)
6. [Router Modules](#router-modules)
7. [Exceptions](#exceptions)
8. [Exception handling](#exception-handling)
9. [URL Conventions](#url-conventions)
10. [CRUD Patterns](#crud-patterns)
11. [Filtering and Collection Queries](#filtering-and-collection-queries)
12. [Actions on Resources](#actions-on-resources)
13. [Route Definition Order](#route-definition-order)
14. [Complex Queries via POST](#complex-queries-via-post)

**[Frontend Naming Conventions](#frontend-naming-conventions)**

1. [General](#general-1)
2. [File Organization](#file-organization)
3. [API Layer](#api-layer)
4. [Components](#components)
5. [Hooks](#hooks)
6. [Type Definitions](#type-definitions)
7. [State Management](#state-management)
8. [Routing](#routing)

---

# Backend Naming Conventions

## General
- Class names should be `PascalCase`.
- Functions, class attributes, variables and methods should be `snake_case`.

## Code Quality Tools

The project uses automated tools to enforce code quality and consistency. Configuration is in `backend/pyproject.toml`.

### Ruff (Linter & Formatter)

**Ruff** is used for linting and code formatting. It's extremely fast and combines functionality from multiple tools (flake8, isort, pyupgrade, etc.).

**Running Ruff:**
```bash
# Format code
ruff format .

# Lint code
ruff check .

# Lint and auto-fix issues
ruff check --fix .
```

**Current configuration:**
- **Target**: Python 3.12
- **Line length**: 120 characters
- **Enabled rules**:
  - `E`, `W` - pycodestyle errors and warnings
  - `F` - pyflakes (undefined names, unused imports)
  - `I` - isort (import sorting)
  - `B` - flake8-bugbear (common bugs and design problems)
  - `UP` - pyupgrade (modernize Python syntax)
- **Ignored rules**:
  - `E501` - Line too long (handled by formatter)
- **Format style**: Double quotes, space indentation, auto line endings

See `[tool.ruff]` in `backend/pyproject.toml` for full configuration.

### Pyright (Type Checker)

**Pyright** enforces strict static type checking to catch type-related bugs before runtime.

**Running Pyright:**
```bash
# Type check all files
pyright

# Type check specific file
pyright src/novels/service.py
```

**Current configuration:**
- **Mode**: Strict type checking enabled
- **Includes**: `src/` directory
- **Excludes**: `src/lib/` (external libraries)
- **Reports enabled**:
  - Unused imports
  - Unused variables
- **Environment**: Configured for dev container (venv at `/app`)

**Type hints are required in strict mode:**
- All function parameters must have type hints (except `self` and `cls`)
- All return types must be specified
- Use `typing` module for complex types (e.g., `list[str]`, `dict[str, Any]`, `Optional[int]`)

See `[tool.pyright]` in `backend/pyproject.toml` for full configuration.

### Running Code Quality Checks

Before committing code, ensure:
```bash
# 1. Format code
ruff format .

# 2. Lint and auto-fix
ruff check --fix .

# 3. Type check
pyright

# 4. Run tests
pytest

# If working on autolabeling features, run
pytest -m "slow or not slow"
```

### VS Code Integration

The dev container includes these extensions pre-configured:
- **Ruff** (`charliermarsh.ruff`) - Auto-format on save, inline linting
- **Pylance** (`ms-python.vscode-pylance`) - Pyright integration, shows type errors inline

Ruff will auto-format on save, and Pylance will show type errors as you code.

## Database Models
- Names of columns should be `snake_case`.
- Table names should describe the thing stored in each row as plural (e.g. `fruits`, `houses`, etc.).
- Properties of `x` (columns in table `xs`) should be called `x_field_name` (e.g. `Fruit.fruit_name` in table named `fruits`).
- If `x` has a ForeignKey to `y`, the corresponding relationships should be defined by `y_of_x` in `x` and `xs_with_y` in `y` (e.g. `fruits_with_colour` in table `colours` and `colour_of_fruit` in table `fruits`).
- If `x` has a ForeignKey to `y`, the ForeignKey column name should be called `y_id` in `x` e.g. `colour_id` in table `fruits`.
- Convention may be broken in the case that breaking a naming convention gives a more descriptive column.

## Pydantic Schemas
- Objects intended for return to users should be self-describing.
- If such an object is associated with a db model, then the object should share the name with the db model, possibly with some suffix attached.
- _Example_:
    ```python
        # db model
        class LabelData(Base):
            some_metadata
            some_large_data
    ```
    ```python
        # pydantic schema
        class LabelData(BaseModel):
            some_metadata
            some_large_data
        
        class LabelDataMeta(BaseModel):
            some_metadata
    ```
- Base classes should end with `Base` (e.g. `LabelOpBase`).
- Pydantic models associated with specific user requests should be of the form `VerbObject` related to what the user wishes to do (e.g. `CreateObject`, `DeleteObject`, `UpdateObject`).
- If a module needs to send an ACK to client, should define a `OperationStatus` pydantic schema, where Operation is the operation that needs to be ACKed. 

## Service Modules
- Names of service functions should follow the rules below: 
    - `query_object` for database queries
    - `modify_object` for database updates
    - `insert_object` for database inserts
    - `remove_object` for database removes
    - `action_object` for more specific actions
    - Optionally, add a `with_restriction` suffix to above names when need to restrict queries to certain objects
    - Optionally, add a `by_method` suffix to above names when method of performing operation is specified (e.g. `modify_label_data_by_stream` vs. `modify_label_data`).
    - For aggregate data, make the object in question plural.
- Parameters should go in the order of
    1. db
    2. other dependencies
    3. primitive data types corresponding to path variables
    4. other data
    5. request body (e.g. pydantic models)
- There should be no keyword arguments here.
- Try to be consistent with parameter order.
- Any dependency that the router layer has should be passed to this layer.
- Insecure queries should be marked as private by an underscore prefix (e.g. `_query_labels_by_label_data_id_insecure`).

## Router Modules
- Names of functions should follow the rules below:
    - `read_object` for GET requests
    - `create_object` for POST requests that create resources
    - `action_object` for POST action endpoints (e.g. `publish_chapter_revision` for `POST /revisions/{revision_id}/publish`)
    - `read_object` for POST endpoints that exist solely for complex request bodies (e.g. `read_flagged_instances` for `POST /filters/{filter_name}/flag-instances`)
    - `update_object` for PATCH requests
    - `delete_object` for DELETE requests
    - Use plural for functions corresponding to endpoints that operate on a collection.
    - Use singular for functions corresponding to endpoints that operate on a single item.
    - Try to use different actions from service modules.
- Parameters should go in the order of
    1. Path parameters
    2. Required query parameters (if applicable)
    3. Request body (if applicable)
    4. Dependencies (e.g. `param : Annotated[Type, Depends(dependency_fn)]`)
    5. Optional query parameters
- Try to be consistent with parameter order.
- Any dependencies that a router needs should be passed to the service layer.

## Exceptions
- Base exception classes should be defined in the top-level `exceptions.py` file (e.g. `DuplicateException`, `NotFoundException`, etc.)
- Exceptions for specific services should be defined in the service-specific `exceptions.py` module.
- Exceptions that describe a certain object matching the description of a top-level exception should follow the format `ObjectTopLevelException` (e.g. `UserNameDuplicateException`, `RawChapterRevisionNotFoundException`) and should inherit from the top-level exception.
- For exceptions that do not fall under a top-level exception, just be descriptive enough and do not match the suffix to a top-level exception (e.g. `RawChapterRevisionMakePrimaryFailedException`).
- For service-specific describing an error that occurs to a specific type of object, top-level exceptions should follow the convention `ObjectTopLevelException` (e.g. `LabelInvalidOperationException`). Inherited exceptions should have `Object` as a prefix, as well as `TopLevelException` as a suffix (e.g. `LabelWordMismatchInvalidOperationException`).

## Exception handling
- Custom exceptions should be defined in `exceptions.py` in each feature directory (e.g. `src/auth/exceptions.py`)
- Custom/pythonic exceptions should be raised in service modules on error, as opposed to returning error codes. Possible raised exceptions must be clearly outlined in docstring.
- Router functions are responsible for handling custom exceptions raised from service modules.
- If an exception is raised, no more db calls should be made to preserve atomicity.

# API Endpoints

Follow RESTful API naming conventions.

## URL Conventions
- Use `kebab-case` for multi-word URL path segments (e.g. `/label-groups`, `/auto-labels`, `/flag-instances`).
- Path parameters use `snake_case` (e.g. `{novel_id}`, `{label_group_id}`) since they map to Python variables.
- Query parameters use `kebab-case`. In FastAPI, this requires an explicit alias:
    ```python
    def read_novels(
        title_contains: str | None = Query(default=None, alias="title-contains"),
    ): ...
    ```
- JSON request/response body keys use `snake_case`.

## CRUD Patterns

| Operation | Method | Pattern | Example |
|-----------|--------|---------|---------|
| Read one | GET | `/objects/{object_id}` | `GET /novels/{novel_id}` |
| Read collection | GET | `/objects` | `GET /novels` |
| Create (standalone) | POST | `/objects` | `POST /novels` |
| Create (owned) | POST | `/parent-objects/{parent_id}/objects` | `POST /novels/{novel_id}/chapters` |
| Update | PATCH | `/objects/{object_id}` | `PATCH /novels/{novel_id}` |
| Delete | DELETE | `/objects/{object_id}` | `DELETE /revisions/{revision_id}` |

## Filtering and Collection Queries
- Bulk querying with filters uses `GET /objects` with query parameters (e.g. `GET /novels?title-contains=alice`).
- When querying child resources, prefer query parameters on the child collection (e.g. `GET /chapters?novel-id=1`).
- Nested URL reads (e.g. `GET /novels/{novel_id}/revisions`) are acceptable when the parent-child relationship is naturally navigated.

## Actions on Resources
- Actions that are not standard CRUD should use `POST` with the action as a URL suffix on the resource:
    ```
    POST /revisions/{revision_id}/publish
    POST /revisions/{revision_id}/make-primary
    POST /revisions/{revision_id}/finalize
    ```
- This distinguishes actions from field updates (`PATCH`) and makes intent explicit.
- For bulk actions, use a `bulk-` prefix on the action segment: `POST /revisions/bulk-publish`.

## Route Definition Order
- Static path segments must be defined **before** dynamic segments that share the same prefix. FastAPI matches routes in definition order, so a dynamic parameter will capture a static segment if it comes first.
- Example: define `GET /novels/mine` before `GET /novels/{novel_id}`, otherwise `mine` is captured as a `novel_id`.

## Complex Queries via POST
- When a query requires a complex request body (e.g. filter configurations with nested options), use `POST` instead of `GET`.
- Example: `POST /filters/{filter_name}/flag-instances` with a JSON body specifying filter parameters.


## Relevant Files

- `backend/src/*/models.py` - Database model definitions
- `backend/src/*/schemas.py` - Pydantic schema definitions
- `backend/src/*/service.py` - Service layer implementations
- `backend/src/*/router.py` - API endpoint definitions
- `backend/src/*/exceptions.py` - Custom exception classes

## See Also

- [architecture.md](architecture.md) - Service architecture overview
- [database-schema.md](database-schema.md) - Database table schemas
- [api-design.md](api-design.md) - REST API patterns

---

# Frontend Naming Conventions

## General
- File names should be `PascalCase.tsx` for React components (including pages, providers), `camelCase.ts` for utilities, API modules, and type definition files.
- Component names should be `PascalCase` (e.g., `ChapterViewer`, `FilterPanel`).
- Functions, variables, and hooks should be `camelCase` (e.g., `handleClick`, `isLoading`, `useAuth`).
- Constants should be `UPPER_SNAKE_CASE` (e.g., `API_BASE_URL`, `MAX_RETRIES`).
- All component exports should be **named exports** (no default exports).

## File Organization
- `src/components/` - Reusable UI components, organized by feature in subdirectories (e.g., `components/novels/`, `components/common/`, `components/layout/`).
- `src/pages/` - Page-level components (route targets). Named `{Feature}Page.tsx` (e.g., `NovelsPage.tsx`, `ChapterReaderPage.tsx`).
- `src/api/` - API client functions grouped by resource (e.g., `novels.ts`, `labels.ts`, `auth.ts`).
- `src/contexts/` - React Context definitions and providers.
- `src/types/` - Shared TypeScript type definitions, one file per resource (e.g., `novel.ts`, `language.ts`).
- `src/assets/` - Static assets (images, fonts, etc.).

## API Layer

### Client Setup
- Use Axios as the HTTP client.
- A centralized Axios instance is configured in `src/api/client.ts` with a request interceptor for authentication (attaches JWT Bearer token).
- **No automatic case transformation is performed.** Case conversion between backend `snake_case` and frontend `camelCase` is handled via manual mapping in each API function (see below).

### Function Naming
- API functions should be `camelCase`, following the pattern `{verb}{Resource}` (e.g., `getNovels`, `createChapter`, `updateNovel`, `deleteRevision`).
- For retrieval by identifier, use `get{Resource}ById` (e.g., `getNovelById`).
- For retrieval of child resources, use `get{Children}By{Parent}` (e.g., `getChaptersByNovel`).
- For creation under a parent, use `create{Child}For{Parent}` (e.g., `createChapterForNovel`).
- Group API functions by resource in separate files under `src/api/`.
- **Every API function must have an explicit return type annotation** (e.g., `Promise<Novel>`, `Promise<LabelGroup[]>`). Untyped returns (`Promise<any>`, or omitted types) are not permitted — the API layer is the boundary where raw backend data becomes typed frontend data.

### Case Mapping Convention
The backend sends and receives `snake_case` JSON keys. The frontend uses `camelCase` TypeScript types. Each API function is responsible for mapping between the two:

```typescript
// src/types/novel.ts — frontend uses camelCase
export interface Novel {
  novelId: number;
  novelTitle: string;
  novelDescription: string | null;
  novelAuthor: string | null;
  novelVisibility: Visibility;
  novelType: NovelType;
  novelParentId: number | null;
  languageCode: string;
}

// src/api/novels.ts — mapping in the API function
export async function getNovelById(novelId: number): Promise<Novel> {
  const response = await apiClient.get(`/novels/${novelId}`);
  const d = response.data;
  return {
    novelId: d.novel_id,
    novelTitle: d.novel_title,
    novelDescription: d.novel_description,
    novelAuthor: d.novel_author,
    novelVisibility: d.novel_visibility,
    novelType: d.novel_type,
    novelParentId: d.novel_parent_id,
    languageCode: d.language_code,
  };
}

export async function createNovel(data: CreateNovel): Promise<Novel> {
  const response = await apiClient.post('/novels', {
    novel_title: data.novelTitle,
    novel_description: data.novelDescription,
    novel_visibility: data.novelVisibility,
    novel_type: data.novelType,
    language_code: data.languageCode,
  });
  // ... map response back to camelCase
}
```

**Why manual mapping?** Some backend responses contain opaque `dict[str, Any]` fields (e.g., `auto_label_model_params`) whose keys are domain-specific and must not be transformed. Manual mapping keeps conversion explicit and safe.

## Components
- Component files should match component name (e.g., `ChapterViewer.tsx` exports `ChapterViewer`).
- Props interfaces should be named `{Component}Props` (e.g., `ChapterViewerProps`, `NovelCardProps`).
- Event handlers should be prefixed with `handle` (e.g., `handleClick`, `handleSubmit`).
- Boolean props should be prefixed with `is`, `has`, `should`, or `can` (e.g., `isLoading`, `hasError`).
- Callback props should be prefixed with `on` (e.g., `onClick`, `onSubmit`, `onChapterChange`).

### Component Example
```typescript
interface ChapterViewerProps {
  revisionId: number;
  labels: Label[];
  editable: boolean;
  onLabelClick: (labelId: number) => void;
}

export function ChapterViewer({ revisionId, labels, editable, onLabelClick }: ChapterViewerProps) {
  const [selectedLabelId, setSelectedLabelId] = useState<number | null>(null);

  const handleLabelClick = (labelId: number) => {
    setSelectedLabelId(labelId);
    onLabelClick(labelId);
  };

  return (/* ... */);
}
```

## Hooks
- Custom hooks should be prefixed with `use` (e.g., `useAuth`, `useNovelData`, `useDebounce`).
- Hook files should be named `use{HookName}.ts` (e.g., `useAuth.ts`).
- Hooks should return objects or tuples, not arrays (unless very simple like `useState`).

## Type Definitions
- Interface and type alias names should be `PascalCase` (e.g., `Novel`, `Label`, `Visibility`).
- Type properties should be `camelCase` (e.g., `novelTitle`, `labelScore`).
- Prefer interfaces for object shapes, type aliases for unions/intersections.
- Co-locate types with the code that uses them when possible; share common types in `src/types/`.

## State Management
- Use React Context for global state (auth, languages, etc.).
- Context providers should be named `{Feature}Provider` (e.g., `AuthProvider`, `LanguageProvider`).
- Context consumer hooks should be named `use{Feature}` (e.g., `useAuth`, `useLanguages`).
- Keep local component state with `useState` when possible.

## Routing
- Route paths should be `kebab-case` (e.g., `/label-groups`, `/chapter-reader`).
- Route parameters use `snake_case` (e.g., `:novel_id`, `:chapter_id`).
- Page component files should be named `{Feature}Page.tsx` (e.g., `NovelsPage.tsx`, `ChapterReaderPage.tsx`).

## Relevant Files

- `frontend/src/api/client.ts` - Axios client configuration
- `frontend/src/api/` - API functions grouped by resource
- `frontend/src/types/` - Shared TypeScript types
- `frontend/src/components/` - Reusable components
- `frontend/src/pages/` - Page-level route components

## See Also

- [ui-requirements.md](ui-requirements.md) - Component specifications and UX requirements
- [api-design.md](api-design.md) - Backend API contracts
- [architecture.md](architecture.md) - System architecture overview
- [testing.md](testing.md) - Backend testing
- [frontend-testing.md](frontend-testing.md) - Frontend testing