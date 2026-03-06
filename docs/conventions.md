# Backend Naming Conventions

**Last Updated**: March 5, 2026  
**Status**: Complete

This document defines naming and structural conventions for the NovelTL backend codebase.

## General
- Class names should be `PascalCase`.
- Functions, class attributes and methods should be `snake_case`.

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

## Service Modules:
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
    5. form data (e.g. pydantic models)
- There should be no keyword arguments here.
- Try to be consistent with parameter order.
- Any dependency that the router layer has should be passed to this layer.
- Insecure queries should be marked as private by an underscore prefix (e.g. `_query_labels_by_label_data_id_insecure`).

## Router Modules
- Names of functions should follow the rules below:
    - `read_object` for GET requests
    - `create_object` for POST requests
    - `update_object` for PATCH requests
    - `delete_object` for DELETE requests
    - For more specific verbs, append one of the four verbs above to denote the specific category (e.g. `update_publish_chapter_revision`).
    - Use plural for functions corresponding to endpoints that operate on a collection.
    - Use singular for functions corresponding to endpoints that operate on a single item.
- Parameters should go in the order of
    1. Path parameters
    2. Required query parameters (if applicable)
    3. Request body (if applicable)
    4. Dependencies (e.g. `param : Annotated[Type, Depends(dependency_fn)]`)
    5. Optional query parameters
- Try to be consistent with parameter order.
- Any dependencies that a router needs should be passed to the service layer.

## Exceptions
- Exceptions describing classes should be defined in the top levels `exceptions.py` file (e.g. `DuplicateException`, `NotFoundException`, etc.)
- Exceptions for specific services should be defined in the service-specific `exceptions.py` module.
- Exceptions that describe a certain object matching the description of a top-level exception should follow the format `ObjectTopLevelException` (e.g. `UserNameDuplicateException`, `RawChapterRevisionNotFoundException`) and should inherit from the top-level exception.
- For exceptions that do not fall under a top-level exception, just be descriptive enough and do not match the suffix to a top-level exception (e.g. `RawChapterRevisionMakePrimaryFailedException`).
- For service-specific describing an error that occurs to a specific type of object, top-level exceptions should follow the convention `ObjectTopLevelException` (e.g. `LabelInvalidOperationException`). Inherited exceptions should have `Object` as a prefix, as well as `TopLevelException` as a suffix (e.g. `LabelWordMismatchInvalidOperationException`).

## Exception handling
- Custom exceptions should be defined in `exceptions.py` in each feature directory (e.g. `src/auth/exeptions.py`)
- Custom/pythonic exceptions should be raised in service modules on error, as opposed to returning error codes. Possible raised exceptions must be clearly outlined in docstring.
- Router functions are responsible for handling custom exceptions raised from service modules.
- If an exception is raised, no more db calls should be made to preserve atomicity.

# API Endpoints
- As a general guideline, try to follow RESTful API naming conventions.
- Separating words should be done with spaces.
- Use `kebab-case`.
- Retrieving objects specified by id should be done through the endpoint `GET objects/{object_id}`.
- Inserting an object owned by another object should be done through the endpoint `POST owning-objects/{owning_object_id}/objects` (e.g. `novels/{novel_id}/raw_chapters`).
- Inserting an object not owned by any other object should be done through the endpoint `POST /objects` (e.g. `POST /novels`).
- Updating an object with specified id should be done through the endpoint `PATCH /objects/{object_id}`.
- Deleting an object with specified id should be done through the endpoint `DELETE /objects/{object_id}`.
- Bulk querying an object by some filters should be done throug the endpoint `GET /objects` (e.g. `GET /raw-chapter-revisions`).
- Use your own judgement for anything else. We will keep updating this part.

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
- File names should be `PascalCase.tsx` for React components, `camelCase.ts` for utilities and non-component files
- Component names should be `PascalCase` (e.g., `ChapterViewer`, `FilterPanel`)
- Functions, variables, and hooks should be `camelCase` (e.g., `handleClick`, `isLoading`, `useAuth`)
- Constants should be `UPPER_SNAKE_CASE` (e.g., `API_BASE_URL`, `MAX_RETRIES`)
- Enums should be `PascalCase` with `UPPER_SNAKE_CASE` values

## File Organization
- `src/components/` - Reusable UI components
- `src/pages/` - Page-level components (route targets)
- `src/api/` - API client functions grouped by resource
- `src/contexts/` - React Context providers
- `src/types/` - TypeScript type definitions
- `src/assets/` - Static assets (images, fonts, etc.)

## API Layer
- API caller functions should be `camelCase` (e.g., `getNovels`, `createLabelGroup`, `updateChapter`)
- Group API functions by resource in separate files under the `/api/` folder (e.g., `novels.ts`, `labels.ts`, `auth.ts`)
- Use Axios as the HTTP client with interceptors for:
  1. **Authentication** - Automatically attach JWT tokens to requests
  2. **Case transformation** - Convert between snake_case (backend) and camelCase (frontend)
- TypeScript types should use `camelCase` field names to follow JavaScript conventions
  - Backend sends: `novel_title` (snake_case)
  - Frontend uses: `novelTitle` (camelCase)
  - Axios interceptors handle automatic conversion

### Axios Client Setup

Create a centralized API client with interceptors:

```typescript
// src/api/client.ts
import axios from 'axios';

// Helper functions for case transformation
function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
}

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function transformKeys(obj: any, transformer: (key: string) => string): any {
  if (Array.isArray(obj)) {
    return obj.map(item => transformKeys(item, transformer));
  }
  if (obj !== null && typeof obj === 'object') {
    return Object.entries(obj).reduce((acc, [key, value]) => {
      acc[transformer(key)] = transformKeys(value, transformer);
      return acc;
    }, {} as any);
  }
  return obj;
}

// Create Axios instance
const apiClient = axios.create({
  baseURL: '/api',  // Adjust to match your backend URL
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: Add auth token and transform to snake_case
apiClient.interceptors.request.use(
  (config) => {
    // Add authentication token
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Transform request data from camelCase to snake_case
    if (config.data) {
      config.data = transformKeys(config.data, camelToSnake);
    }
    
    // Transform query params from camelCase to snake_case
    if (config.params) {
      config.params = transformKeys(config.params, camelToSnake);
    }
    
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Transform to camelCase
apiClient.interceptors.response.use(
  (response) => {
    // Transform response data from snake_case to camelCase
    if (response.data) {
      response.data = transformKeys(response.data, snakeToCamel);
    }
    return response;
  },
  (error) => {
    // Transform error response data as well
    if (error.response?.data) {
      error.response.data = transformKeys(error.response.data, snakeToCamel);
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

### API Function Naming Pattern
```typescript
// Format: {verb}{Resource}{ByIdentifier?}
getNovels()           // GET /novels
getNovelById(id)      // GET /novels/{id}
createNovel(data)     // POST /novels
updateNovel(id, data) // PATCH /novels/{id}
deleteNovel(id)       // DELETE /novels/{id}

// For nested resources
getChaptersByNovel(novelId)           // GET /chapters?novel_id={novelId}
createChapterForNovel(novelId, data)  // POST /novels/{novelId}/chapters
```

### API Function Implementation Example

```typescript
// src/types/novel.ts
export interface Novel {
  novelId: number;           // Matches backend's novel_id
  novelTitle: string;        // Matches backend's novel_title
  novelDescription: string | null;
  novelAuthor: string | null;
  novelVisibility: number;
  novelType: string;
  languageCode: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateNovelRequest {
  novelTitle: string;
  novelDescription?: string;
  novelAuthor?: string;
  novelVisibility: number;
  novelType: string;
  languageCode: string;
}

// src/api/novels.ts
import apiClient from './client';
import type { Novel, CreateNovelRequest } from '../types/novel';

export async function getNovels(titleContains?: string): Promise<Novel[]> {
  const response = await apiClient.get<Novel[]>('/novels', {
    params: { titleContains },  // Will be transformed to title_contains
  });
  return response.data;  // Already in camelCase thanks to interceptor
}

export async function getNovelById(id: number): Promise<Novel> {
  const response = await apiClient.get<Novel>(`/novels/${id}`);
  return response.data;
}

export async function createNovel(data: CreateNovelRequest): Promise<Novel> {
  const response = await apiClient.post<Novel>('/novels', data);
  // data is transformed to snake_case before sending
  // response is transformed to camelCase before returning
  return response.data;
}

export async function updateNovel(
  id: number,
  data: Partial<CreateNovelRequest>
): Promise<Novel> {
  const response = await apiClient.patch<Novel>(`/novels/${id}`, data);
  return response.data;
}

export async function deleteNovel(id: number): Promise<void> {
  await apiClient.delete(`/novels/${id}`);
}
```

## Components
- Component files should match component name (e.g., `ChapterViewer.tsx` exports `ChapterViewer`)
- Props interfaces should be named `{Component}Props` (e.g., `ChapterViewerProps`)
- Event handlers should be prefixed with `handle` (e.g., `handleClick`, `handleSubmit`, `handleChapterChange`)
- Boolean props should be prefixed with `is`, `has`, `should`, or `can` (e.g., `isLoading`, `hasError`, `shouldSync`)
- Callback props should be prefixed with `on` (e.g., `onClick`, `onSubmit`, `onChapterChange`)

### Component Example
```typescript
interface ChapterViewerProps {
  revisionId: number;
  labels: Label[];
  editable: boolean;
  onLabelClick: (labelId: number) => void;
  onLabelCreate: (start: number, end: number, word: string) => void;
}

export function ChapterViewer({ revisionId, labels, editable, onLabelClick, onLabelCreate }: ChapterViewerProps) {
  const [selectedLabelId, setSelectedLabelId] = useState<number | null>(null);
  
  const handleLabelClick = (labelId: number) => {
    setSelectedLabelId(labelId);
    onLabelClick(labelId);
  };
  
  return (/* ... */);
}
```

## Hooks
- Custom hooks should be prefixed with `use` (e.g., `useAuth`, `useNovelData`, `useDebounce`)
- Hook files should be named `use{HookName}.ts` (e.g., `useAuth.ts`, `useNovelData.ts`)
- Hooks should return objects or tuples, not arrays (unless very simple like `useState`)

### Hook Example
```typescript
// useAuth.ts
export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  return {
    user,
    isLoading,
    login,
    logout,
    isAuthenticated: user !== null,
  };
}
```

## Type Definitions
- Interface names should be `PascalCase` (e.g., `Novel`, `Label`, `ChapterViewerProps`)
- Type aliases should be `PascalCase` (e.g., `NovelId`, `Visibility`)
- Prefer interfaces for object shapes, type aliases for unions/intersections
- Co-locate types with the code that uses them when possible
- Share common types in `src/types/` directory

## State Management
- Use React Context for global state (auth, theme, etc.)
- Context providers should be named `{Feature}Provider` (e.g., `AuthProvider`, `ThemeProvider`)
- Context consumer hooks should be named `use{Feature}` (e.g., `useAuth`, `useTheme`)
- Keep local component state with `useState` when possible
- Use `useReducer` for complex state logic

## Routing
- Route paths should be `kebab-case` (e.g., `/label-groups/{id}`, `/chapter-viewer`)
- Route component files should match the route name (e.g., `LabelGroupsPage.tsx`, `ChapterViewerPage.tsx`)

## Styling
- CSS class names should be `kebab-case` (e.g., `.chapter-viewer`, `.label-tooltip`)
- CSS modules or styled-components preferred for component-scoped styles
- Global styles in `src/index.css` or similar

## Comments and Documentation
- Use JSDoc comments for public API functions and complex components
- Inline comments should explain "why", not "what"
- TODO comments should include assignee and date: `// TODO(username, 2026-03-05): Fix edge case`

## Relevant Files

- `frontend/src/` - Frontend source code root
- `frontend/src/api/` - API client functions
- `frontend/src/types/` - Shared TypeScript types
- `frontend/src/components/` - Reusable components

## See Also

- [ui-requirements.md](ui-requirements.md) - Component specifications and UX requirements
- [api-design.md](api-design.md) - Backend API contracts
- [architecture.md](architecture.md) - System architecture overview 