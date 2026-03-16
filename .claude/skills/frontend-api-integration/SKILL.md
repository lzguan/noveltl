---
name: frontend-api-integration
description: 4-stage process for generating frontend API integration tests and API functions. Use when user asks to write, audit, or generate frontend API tests or API client functions.
---

# Frontend API Integration Skill

This skill implements a 4-stage pipeline for generating and validating frontend API integration tests and API client functions. Each stage produces a report or code output, and stages should be executed sequentially.

The user may ask you to run all 4 stages, or a subset. If the user asks for a specific stage, skip to that stage. If the user doesn't specify, start from Stage 1.

**Scope control:** The user may specify a single module (e.g., "novels"), a list of modules, or "all". If not specified, ask which modules to target. Available modules correspond to files in `frontend/src/api/` (e.g., `auth`, `novels`, `languages`, `labels`, `users`). Run each stage for all in-scope modules before advancing to the next stage.

---

## Reference Files

These files are the source of truth for conventions, expected test cases, and architecture:

| Purpose | File |
|---------|------|
| Frontend testing standards | `docs/frontend-testing.md` |
| Naming & API conventions | `docs/conventions.md` (especially "Frontend Naming Conventions" → "API Layer") |
| API design decisions | `docs/api-design.md` |
| Backend testing patterns | `docs/testing.md` |

**Always read `docs/frontend-testing.md` and `docs/conventions.md` at the start of any stage.** These are the authoritative references for what tests should exist, how API functions should be structured, and what conventions to follow. Do not rely solely on the instructions in this skill file — the docs may have been updated since this skill was written.

---

## Stage 1: Backend Endpoint Analysis

**Goal:** Understand every backend endpoint's contract — URL, method, auth requirements, request/response schemas, and error codes — for the in-scope modules.

### Steps

1. **Read the backend router file** for each in-scope module:
   - `backend/src/{module}/router.py`

   For each endpoint, extract:
   - HTTP method and URL path (including any `prefix` set on the router or in `main.py`)
   - Path parameters and query parameters (note `Query(alias=...)` for kebab-case aliases)
   - Request body schema (Pydantic model name)
   - Response model (Pydantic model name, or status code for no-body responses)
   - Auth dependency (`get_current_user` vs `get_optional_user` vs none)
   - Exception handling: which exceptions are caught and what HTTP status codes they map to

2. **Read the backend schema file** for each in-scope module:
   - `backend/src/{module}/schemas.py`

   For each Pydantic model, extract:
   - All fields with types
   - Validators and constraints (min length, regex, etc.)
   - Which models are request vs response schemas

3. **Read the backend exceptions file** for each in-scope module:
   - `backend/src/{module}/exceptions.py`
   - Also read `backend/src/exceptions.py` for base exception classes

4. **Check how routers are registered** in `backend/src/main.py` — look for any URL prefixes applied via `app.include_router(..., prefix=...)`.

### Output: Stage 1 Report

Produce a table per module with the following columns:

```
| Method | Path | Auth | Request Schema | Response Schema | Error Codes | Notes |
```

Where:
- **Path** is the full URL path (including any router prefix)
- **Auth** is `required`, `optional`, or `none`
- **Request Schema** is the Pydantic model name (or "—" for GET/DELETE with no body)
- **Response Schema** is the Pydantic model name (or "204 No Content", etc.)
- **Error Codes** lists all HTTP status codes the endpoint can return (e.g., `404, 409, 401`)
- **Notes** captures anything non-obvious (e.g., "returns Meta variant without text field", "kebab-case query alias", "discriminated union request body")

Also list every request and response schema with their fields and types.

---

## Stage 2: Frontend Test Audit

**Goal:** Compare existing frontend tests against the expected test cases defined in `docs/frontend-testing.md`, and flag tests that are incorrect or missing.

### Steps

1. **Read `docs/frontend-testing.md`** — specifically the "Test Cases by Module" section. This defines the required test cases per API function.

2. **Read each existing test file** in `frontend/src/api/__test__/`:
   - For each `describe`/`it` block, determine which test case from the doc it corresponds to.
   - Verify the test is correct:
     - Does it mock the right HTTP method? (`client.get` vs `client.post` vs `client.patch` vs `client.delete`)
     - Does the mock return data with correct `snake_case` keys matching the backend schema?
     - Does it assert the correct URL (including leading `/`)?
     - Does it assert the correct query parameter keys (including kebab-case aliases)?
     - Does it verify response mapping from `snake_case` → `camelCase`?
     - Does it verify request mapping from `camelCase` → `snake_case`?
     - For error tests: does it mock a rejected promise and assert the right error type/message?
     - Does it follow the type safety patterns from the doc (i.e., `satisfies` and `expectTypeOf`)?

3. **Read each existing API function file** in `frontend/src/api/`:
   - For each function, verify the test covers all the test case categories listed in the doc.

4. **Cross-reference with Stage 1 output:**
   - Are there backend endpoints with no corresponding frontend API function? (These go in the "not yet implemented" list but tests can still be specified.)
   - Are there frontend API functions that don't match any backend endpoint? (These are orphaned.)

### Output: Stage 2 Report

Produce three lists:

**1. Faulty tests** — tests that exist but are incorrect:
```
| File | Test Name | Issue | Expected |
```

**2. Missing tests** — test cases defined in the doc that have no corresponding `it()` block:
```
| Module | Function | Test Case # | Description |
```

**3. Missing API functions** — backend endpoints with no frontend API function:
```
| Module | Endpoint | Suggested Function Name |
```

---

## Stage 3: Fix Tests and Generate New Tests

**Goal:** Fix all faulty tests from Stage 2, write all missing tests, and create stub API functions where needed so tests can compile.

### Steps

1. **Fix faulty tests** identified in Stage 2. For each fix:
   - Read the current test code
   - Read the corresponding API function to understand what it actually does
   - Fix the test to match the expected behavior from the doc

2. **Generate missing tests** for existing API functions. For each missing test case:
   - Follow the test patterns defined in `docs/frontend-testing.md` (mock setup, arrange/act/assert structure)
   - Use the same file organization (`__test__/` directory, one test file per API module)
   - Follow these conventions from the doc:
     - `vi.mock('../client')` at the module level
     - `vi.mocked(client.get).mockResolvedValue(...)` for happy path
     - `vi.mocked(client.get).mockRejectedValue(...)` for error cases
     - `satisfies` operator for compile-time type checking of test data
     - `expectTypeOf` for verifying function return types
     - `afterEach(() => vi.restoreAllMocks())` for mock cleanup

3. **Create stub API functions** for backend endpoints that don't have frontend implementations yet. Stubs must:
   - Have the correct function signature (name, parameters, return type) following the naming convention in `docs/conventions.md`:
     - `get{Resource}` / `get{Resource}ById` / `get{Children}By{Parent}` for GET
     - `create{Resource}` / `create{Child}For{Parent}` for POST
     - `update{Resource}` for PATCH
     - `delete{Resource}` for DELETE
     - `{action}{Resource}` for POST action endpoints (e.g., `publishRevision`)
   - Have the correct return type annotation (e.g., `Promise<Novel>`, `Promise<LabelGroup[]>`)
   - Throw `new Error('Not implemented')` as the body
   - Include request and response mapper stubs if needed (following the existing pattern of `mapXxx` and `mapCreateXxxRequest` private functions)

4. **Create stub TypeScript types** in `frontend/src/types/` if any response/request schemas don't have corresponding frontend interfaces yet. Follow the existing pattern:
   - Response types match the backend response schema fields in `camelCase`
   - Request types named `Create{Resource}`, `Update{Resource}`
   - Use `Omit<>` for meta variants (e.g., `type RawChapterRevisionMeta = Omit<RawChapterRevision, 'rawChapterRevisionText'>`)

5. **Write tests for stubs too** — even though the API function throws "Not implemented", the test structure should be complete. When Stage 4 fills in the implementation, the tests should pass without modification.

### Conventions Checklist

Before writing any code, verify you are following these conventions by checking the relevant docs:

- [ ] Test file location: `frontend/src/api/__test__/{module}.test.ts`
- [ ] Import `{ vi } from 'vitest'` (or rely on globals — check `vite.config.ts` for `globals: true`)
- [ ] Import `client from '../client'` and `vi.mock('../client')`
- [ ] Import types from `../../types/{module}`
- [ ] Use `afterEach(() => vi.restoreAllMocks())`
- [ ] Mock data uses `snake_case` keys matching backend Pydantic schema field names exactly
- [ ] Expected results use `camelCase` keys matching frontend TypeScript interfaces exactly
- [ ] URL strings have a leading `/` (e.g., `'/novels'`, not `'novels'`)
- [ ] Query param keys use kebab-case aliases where the backend defines them (e.g., `'title-contains'`, `'novel-id'`, `'is-public'`)
- [ ] Use `satisfies` operator on expected result objects in `toEqual()` calls
- [ ] Use `expectTypeOf` for compile-time return type assertions
- [ ] Error tests use `mockRejectedValue` with `AxiosError` (or appropriate error constructor)
- [ ] Every API function has an explicit return type annotation (e.g., `Promise<Novel>`)
- [ ] API function names follow `{verb}{Resource}` convention from `docs/conventions.md`
- [ ] Request mappers are named `mapCreate{Resource}Request` / `mapUpdate{Resource}Request`
- [ ] Response mappers are named `map{Resource}` / `map{Resource}Meta`

### Output

- Updated/new test files in `frontend/src/api/__test__/`
- Stub API functions in `frontend/src/api/` (if needed)
- Stub types in `frontend/src/types/` (if needed)
- Brief summary of changes made

After writing code, run all three from `frontend/`:
```bash
npx vitest run --reporter=verbose
npx tsc -p tsconfig.app.json --noEmit
npx eslint src/
```
Stubs will fail at runtime — that's expected. But all existing tests must pass, `tsc` must exit clean, and ESLint must report 0 errors.

---

## Stage 4: Implement API Functions

**Goal:** Replace all stub API functions with real implementations, and verify all tests pass.

### Steps

1. **Read the Stage 1 report** (or re-derive it) to know each endpoint's exact contract.

2. **Read existing implemented API functions** to understand the established patterns:
   - `frontend/src/api/novels.ts` — most complete example (response mappers, request mappers, query params with kebab-case aliases, collection endpoints)
   - `frontend/src/api/labels.ts` — label group CRUD example
   - `frontend/src/api/languages.ts` — simple read-only example
   - `frontend/src/api/auth.ts` — special case (form-encoded, token handling)

3. **For each stub API function**, implement it following these patterns:

   **Response mapper pattern:**
   ```typescript
   /* eslint-disable @typescript-eslint/no-explicit-any */
   const mapResource = (data: any): ResourceType => ({
       camelCaseField: data.snake_case_field,
       // ... all fields
   })
   /* eslint-enable @typescript-eslint/no-explicit-any */
   ```

   **Request mapper pattern:**
   ```typescript
   const mapCreateResourceRequest = (data: CreateResource) => ({
       snake_case_field: data.camelCaseField,
       // ... all fields
   })
   ```

   **GET single resource:**
   ```typescript
   export const getResourceById = async (resourceId: number): Promise<Resource> => {
       const result = await client.get(`/resources/${resourceId}`)
       return mapResource(result.data)
   }
   ```

   **GET collection with query params:**
   ```typescript
   export const getResources = async (filterParam?: string): Promise<Resource[]> => {
       const result = await client.get('/resources', {
           params: {
               'kebab-alias': filterParam
           }
       })
       return result.data.map(mapResource)
   }
   ```

   **POST create:**
   ```typescript
   export const createResource = async (request: CreateResource): Promise<Resource> => {
       const result = await client.post('/resources', mapCreateResourceRequest(request))
       return mapResource(result.data)
   }
   ```

   **POST create under parent:**
   ```typescript
   export const createChildForParent = async (parentId: number, request: CreateChild): Promise<Child> => {
       const result = await client.post(`/parents/${parentId}/children`, mapCreateChildRequest(request))
       return mapChild(result.data)
   }
   ```

   **PATCH update:**
   ```typescript
   export const updateResource = async (resourceId: number, request: UpdateResource): Promise<Resource> => {
       const result = await client.patch(`/resources/${resourceId}`, mapUpdateResourceRequest(request))
       return mapResource(result.data)
   }
   ```

   **DELETE:**
   ```typescript
   export const deleteResource = async (resourceId: number): Promise<DeleteResourceStatus> => {
       const result = await client.delete(`/resources/${resourceId}`)
       return mapDeleteStatus(result.data)
   }
   ```

   **POST action:**
   ```typescript
   export const publishResource = async (resourceId: number): Promise<Resource> => {
       const result = await client.post(`/resources/${resourceId}/publish`)
       return mapResource(result.data)
   }
   ```

4. **Critical checks before finalizing:**
   - Every URL string has a leading `/`
   - Every function has an explicit return type annotation
   - Request mappers correctly convert all fields from `camelCase` to `snake_case`
   - Response mappers correctly convert all fields from `snake_case` to `camelCase`
   - Query parameter keys use the exact kebab-case alias from the backend router's `Query(alias=...)`
   - No `any` escapes outside of mapper functions (and those are wrapped in eslint-disable comments)
   - Collection endpoints return `result.data.map(mapXxx)`, not `mapXxx(result.data)`

5. **Run tests, type check, and lint:**
   ```bash
   cd frontend && npx vitest run --reporter=verbose
   npx tsc -p tsconfig.app.json --noEmit
   npx eslint src/
   ```
   All three must be clean. Common issues:
   - **tsc**: Unused imports (`noUnusedLocals`); `null` assigned to `?:` field (check backend schema — if backend returns `null`, type should be `T | null` not `T | undefined`); `satisfies` surfaces type mismatches that esbuild silently ignores
   - **eslint**: `no-explicit-any` — do NOT use file-level disables. In test files, use `makeAxiosError` from `src/api/__test__/testUtils.ts` instead of `new AxiosError(...) as any`. In source files, wrap unavoidable `any` in `/* eslint-disable */` / `/* eslint-enable */` blocks scoped as tightly as possible

### Output

- Completed API functions in `frontend/src/api/`
- All tests passing, `tsc` exits clean
- Brief summary of what was implemented

---

## General Guidelines

### When in doubt, check the docs
The `docs/frontend-testing.md` file defines the exact test cases. The `docs/conventions.md` file defines naming rules. Always defer to these over patterns you infer from existing code — the docs may have been updated to fix issues in the existing code.

### Don't skip error cases
Error propagation tests (`mockRejectedValue` with `AxiosError`) catch real bugs. The API functions currently don't do custom error handling (they let Axios errors propagate), but tests should still verify this behavior because:
- A future refactor might accidentally swallow errors
- Some functions (like `login`) do have custom error handling

### Keep mappers private
Response and request mapper functions (`mapNovel`, `mapCreateNovelRequest`, etc.) should not be exported. They are implementation details of the API layer. Tests verify the mapping indirectly by checking the return value of the public API function.

### One test file per API module
Don't split tests across multiple files for the same module. Keep all tests for `novels.ts` in `__test__/novels.test.ts`.

### Module file organization
Within each API module file, follow this section order (matching the existing pattern in `novels.ts`):
1. Imports
2. Response mappers (with eslint-disable/enable comments around the `any` block)
3. Request mappers
4. API functions (exported)
