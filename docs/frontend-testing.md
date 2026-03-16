# Frontend Testing Guide

**Last Updated**: March 10, 2026  
**Status**: Complete

This document defines standards and expected test cases for frontend API integration tests. These tests verify that each API function in `src/api/` correctly calls the backend, maps data between `snake_case` and `camelCase`, and handles errors appropriately.

For backend testing, see [testing.md](testing.md). For API design context, see [api-design.md](api-design.md).

---

## Table of Contents

1. [Architecture Decisions](#architecture-decisions)
2. [Test Organization](#test-organization)
3. [Running Tests](#running-tests)
4. [Test Patterns](#test-patterns)
5. [Test Cases by Module](#test-cases-by-module)

---

## Architecture Decisions

### Unit tests with mocked HTTP client

Tests mock the Axios client (`src/api/client.ts`) at the module level using `vi.mock`. No real HTTP requests are made. This tests the API function logic in isolation: correct URLs, parameters, headers, request body mapping, response mapping, and error handling.

### Why not MSW or integration tests?

MSW (Mock Service Worker) intercepts at the network level — useful for component integration tests but heavier than needed for testing API function logic. The current approach is simpler and faster: mock `client.get`/`client.post`/etc. directly, assert on call arguments and return values. MSW can be added later for component-level tests.

### snake_case ↔ camelCase boundary

The API layer is the sole boundary where backend `snake_case` keys are mapped to frontend `camelCase` types (see [conventions.md](conventions.md#case-mapping-convention)). Tests must verify this mapping in both directions:
- **Response mapping**: mock `client.get` returning `{ snake_case_field: value }` → assert the function returns `{ camelCaseField: value }`
- **Request mapping**: call an API function with `{ camelCaseField: value }` → assert `client.post` was called with `{ snake_case_field: value }`

---

## Test Organization

Test files are co-located with the API modules in `__test__/` directories:

```
frontend/src/api/
├── client.ts
├── auth.ts
├── novels.ts
├── languages.ts
├── labels.ts
├── users.ts
├── token.ts
├── errors.ts
└── __test__/
    ├── auth.test.ts
    ├── novels.test.ts
    ├── languages.test.ts
    ├── labels.test.ts
    └── users.test.ts
```

Each test file corresponds to one API module. No test file for `client.ts`, `token.ts`, or `errors.ts` — these are tested indirectly.

---

## Running Tests

All commands run from `frontend/`:

```bash
npx vitest                    # Watch mode (default)
npx vitest run                # Single run
npx vitest run src/api/       # API tests only
npx vitest run --reporter=verbose  # Detailed output
```

---

## Test Patterns

### Standard mock setup

```typescript
import { vi } from 'vitest'
import client from '../client'

vi.mock('../client')
```

This auto-mocks the entire client module. Use `vi.mocked(client.get)` to access the mock and set return values.

### Happy path test structure

```typescript
it('should fetch and map a novel by ID', async () => {
    // Arrange: mock the HTTP response with snake_case keys
    vi.mocked(client.get).mockResolvedValue({
        data: {
            novel_id: 1,
            novel_title: 'Test Novel',
            // ... all snake_case fields
        }
    })

    // Act: call the API function
    const result = await getNovelById(1)

    // Assert: correct URL called
    expect(client.get).toHaveBeenCalledWith('/novels/1')

    // Assert: response mapped to camelCase
    expect(result).toEqual({
        novelId: 1,
        novelTitle: 'Test Novel',
        // ... all camelCase fields
    })
})
```

### Error test structure

```typescript
it('should propagate axios errors', async () => {
    vi.mocked(client.get).mockRejectedValue(
        new AxiosError('Not Found', '404', undefined, undefined, {
            status: 404,
            data: { detail: 'Novel not found' },
        } as any)
    )

    await expect(getNovelById(999)).rejects.toThrow()
})
```

### Request body mapping test structure

```typescript
it('should map camelCase request to snake_case body', async () => {
    vi.mocked(client.post).mockResolvedValue({
        data: { /* snake_case response */ }
    })

    await createNovel({
        novelTitle: 'New Novel',
        novelVisibility: 'public',
        // ... camelCase fields
    })

    expect(client.post).toHaveBeenCalledWith('/novels', {
        novel_title: 'New Novel',
        novel_visibility: 'public',
        // ... snake_case fields
    })
})
```

### Collection endpoint test structure

```typescript
it('should map each item in a collection response', async () => {
    vi.mocked(client.get).mockResolvedValue({
        data: [
            { language_code: 'en', language_name: 'English' },
            { language_code: 'zh', language_name: 'Chinese' },
        ]
    })

    const result = await getLanguages()

    expect(result).toHaveLength(2)
    expect(result[0]).toEqual({ languageCode: 'en', languageName: 'English' })
})
```

### Query parameter test structure

```typescript
it('should pass optional query params when provided', async () => {
    vi.mocked(client.get).mockResolvedValue({ data: [] })

    await getNovels('alice')

    expect(client.get).toHaveBeenCalledWith('/novels', {
        params: { 'title-contains': 'alice' }
    })
})

it('should pass undefined for omitted optional params', async () => {
    vi.mocked(client.get).mockResolvedValue({ data: [] })

    await getNovels()

    expect(client.get).toHaveBeenCalledWith('/novels', {
        params: { 'title-contains': undefined }
    })
})
```

### Mock reset

Use `beforeEach` or `afterEach` to reset mocks when tests in a describe block share setup:

```typescript
afterEach(() => {
    vi.restoreAllMocks()
})
```

---

## Type Safety in Tests

API boundary tests must ensure strict TypeScript type safety to prevent functions from silently returning `any` and to ensure mocked test data perfectly matches our interfaces. Tests should enforce type safety in two ways:

1. **Test-Data Checking (The `satisfies` operator)**
When hardcoding expected return objects in `toEqual()`, use the TypeScript `satisfies` operator. This ensures the test data strictly conforms to the expected frontend interface (e.g., catching misspelled camelCase keys) without manually declaring separate variables.
2. **Compile-Time Checking (`expectTypeOf`)**
Use Vitest's `expectTypeOf` to verify the actual function signature returns the correct type and hasn't degraded to `any` or `unknown`.

### Type Safety Example

```typescript
import { expectTypeOf } from 'vitest'
import { getLanguages } from '../languages'
import { type Language } from '../../types/language'
import client from '../client'

it('should return a list of languages with strict typing', async () => {
    // Arrange: Mock the snake_case backend response
    vi.mocked(client.get).mockResolvedValue({
        data: [
            { language_code: 'en', language_name: 'English' },
            { language_code: 'zh', language_name: 'Chinese' }
        ]
    })

    // Act
    const result = await getLanguages()

    // Assert 1: Compile-time check (Ensures getLanguages() returns Promise<Language[]>)
    expectTypeOf(result).toEqualTypeOf<Language[]>()

    // Assert 2: Runtime value check with `satisfies` (Ensures test data is valid)
    expect(result).toEqual([
        { languageCode: 'en', languageName: 'English' },
        { languageCode: 'zh', languageName: 'Chinese' }
    ] satisfies Language[]) 
})

```

**Note:** Avoid using the `as` keyword (e.g., `as Language[]`) for test assertions, as it forces TypeScript to ignore missing or incorrect properties in your mock data. Always use `satisfies`.

---

## Test Cases by Module

Each section lists the required test cases per API function. Categories:

- **Call** — Verifies correct HTTP method, URL, headers, and query/path params.
- **Request mapping** — Verifies camelCase input is sent as snake_case body.
- **Response mapping** — Verifies snake_case response is returned as camelCase.
- **Error** — Verifies error handling (thrown exceptions, missing fields).
- **Edge** — Verifies behaviour with optional/missing parameters.

---

### auth.ts

#### `login(formData)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `POST /token` with form data and `Content-Type: application/x-www-form-urlencoded` header |
| 2 | Response | Sets token in localStorage when `access_token` is present in response |
| 3 | Error | Throws `AuthenticationError` when response has no `access_token` |
| 4 | Error | Propagates Axios error on network/server failure (401, 404) |

---

### users.ts

> **Note**: This module is currently empty. Tests should be written against the expected API function signatures, matching the backend endpoints below.

#### `register(request)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `POST /register` with snake_case request body |
| 2 | Request mapping | Maps `{ userName, userPassword, userType }` to `{ user_name, user_password, user_type }` |
| 3 | Response mapping | Maps `{ user_id, user_name, user_type }` to `{ userId, userName, userType }` |
| 4 | Error | Propagates 409 (duplicate username) |
| 5 | Error | Propagates 400 (data too long) |

#### `createUser(request)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `POST /users` with snake_case request body |
| 2 | Request mapping | Maps `{ userName, userPassword, userType }` to `{ user_name, user_password, user_type }` |
| 3 | Response mapping | Maps `{ user_id, user_name, user_type }` to `{ userId, userName, userType }` |
| 4 | Error | Propagates 401 (insufficient permissions) |
| 5 | Error | Propagates 409 (duplicate username) |

#### `getCurrentUser()`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /users/me` |
| 2 | Response mapping | Maps `{ user_id, user_name, user_type }` to `{ userId, userName, userType }` |
| 3 | Error | Propagates 401 (not authenticated) |

#### `getUserByName(userName)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /users/{userName}` |
| 2 | Response mapping | Maps `{ user_id, user_name, user_type }` to `{ userId, userName, userType }` |
| 3 | Error | Propagates 404 (user not found) |

#### `deleteCurrentUser()`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `DELETE /users/me` |
| 2 | Response mapping | Maps `{ status, detail }` correctly |
| 3 | Error | Propagates 404 (user not found) |

#### `deleteUser(userId)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `DELETE /users/{userId}` |
| 2 | Response mapping | Maps `{ status, detail }` correctly |
| 3 | Error | Propagates 404 (user not found) |
| 4 | Error | Propagates 401 (insufficient permissions) |

---

### languages.ts

#### `getLanguages()`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /languages` |
| 2 | Response mapping | Maps each item: `{ language_code, language_name }` → `{ languageCode, languageName }` |
| 3 | Edge | Returns empty array when backend returns `[]` |

#### `getLanguageByCode(languageCode)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /languages/{languageCode}` with code in URL path |
| 2 | Response mapping | Maps `{ language_code, language_name }` → `{ languageCode, languageName }` |
| 3 | Error | Propagates 404 (language not found) |

---

### novels.ts

#### `getNovels(titleContains?)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /novels` with `title-contains` query param |
| 2 | Response mapping | Maps each novel from snake_case to camelCase |
| 3 | Edge | Passes `title-contains: undefined` when `titleContains` is omitted |
| 4 | Edge | Returns empty array when backend returns `[]` |

#### `getNovelsMine(editable, titleContains?)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /novels/mine` with `editable` and `title-contains` params |
| 2 | Response mapping | Maps each novel from snake_case to camelCase |
| 3 | Edge | Passes `title-contains: undefined` when omitted |

#### `getNovelById(novelId)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /novels/{novelId}` |
| 2 | Response mapping | Maps all novel fields from snake_case to camelCase |
| 3 | Response mapping | Handles nullable fields (`novel_description`, `novel_author`, `novel_parent_id`) correctly when `null` |
| 4 | Error | Propagates 404 (novel not found / no permission) |

#### `getChaptersByNovel(novelId, start?, end?)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /chapters` with `novel-id`, `start`, `end` query params |
| 2 | Response mapping | Maps each chapter from snake_case to camelCase |
| 3 | Edge | Omitted `start`/`end` passed as `undefined` |
| 4 | Error | Propagates 404 (novel not found) |

#### `getChapterById(chapterId)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /chapters/{chapterId}` |
| 2 | Response mapping | Maps chapter fields from snake_case to camelCase |
| 3 | Error | Propagates 404 |

#### `getChapterRevisionById(revisionId)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /revisions/{revisionId}` |
| 2 | Response mapping | Maps all revision fields including `raw_chapter_revision_text` |
| 3 | Response mapping | Returns full `RawChapterRevision` (not meta — includes text field) |
| 4 | Error | Propagates 404 |

#### `getChapterRevisionsByNovel(novelId, start?, end?, isPublic?, isPrimary?, isFinal?)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /novels/{novelId}/revisions` with all query params (kebab-case aliases) |
| 2 | Response mapping | Maps each item as `RawChapterRevisionMeta` (no text field) |
| 3 | Edge | All optional params omitted → passed as `undefined` |
| 4 | Edge | Boolean query params serialized correctly |
| 5 | Error | Propagates 404 |

#### `getChapterRevisionsByChapter(chapterId, isPublic?, isPrimary?)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /chapters/{chapterId}/revisions` with query params |
| 2 | Response mapping | Maps each item as `RawChapterRevisionMeta` |
| 3 | Error | Propagates 404 |

#### `createNovel(request)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `POST /novels` |
| 2 | Request mapping | Maps `{ novelTitle, novelDescription, ... }` → `{ novel_title, novel_description, ... }` |
| 3 | Response mapping | Maps response novel from snake_case to camelCase |
| 4 | Error | Propagates 404 (language not found) |
| 5 | Error | Propagates 400 (data too long) |

#### `createChapterForNovel(novelId, request)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `POST /novels/{novelId}/chapters` |
| 2 | Request mapping | Maps `{ rawChapterNum }` → `{ raw_chapter_num }` |
| 3 | Response mapping | Maps chapter response from snake_case to camelCase |
| 4 | Error | Propagates 404 (novel not found) |
| 5 | Error | Propagates 409 (duplicate chapter number) |

#### `createRevisionForChapter(chapterId, request)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `POST /chapters/{chapterId}/revisions` |
| 2 | Request mapping | Maps `{ rawChapterRevisionTitle, rawChapterRevisionText }` → snake_case |
| 3 | Response mapping | Maps full revision response from snake_case to camelCase |
| 4 | Error | Propagates 404 (chapter not found) |
| 5 | Error | Propagates 400 (data too long) |

> **Not yet implemented** — The following backend endpoints do not yet have frontend API functions. Tests for these should be written when the functions are implemented:
> - `updateNovel` → `PATCH /novels/{novelId}`
> - `updateRevision` → `PATCH /revisions/{revisionId}`
> - `publishRevision` → `POST /revisions/{revisionId}/publish`
> - `makeRevisionPrimary` → `POST /revisions/{revisionId}/make-primary`
> - `finalizeRevision` → `POST /revisions/{revisionId}/finalize`
> - `deleteRevision` → `DELETE /revisions/{revisionId}`

---

### labels.ts

#### `getLabelGroupsByNovel(novelId)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /label-groups` with `novel-id` query param |
| 2 | Response mapping | Maps each `{ label_group_id, label_group_name, novel_id }` → camelCase |
| 3 | Edge | Returns empty array when backend returns `[]` |

#### `createLabelGroup(request)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `POST /label-groups` |
| 2 | Request mapping | Maps `{ labelGroupName, novelId }` → `{ label_group_name, novel_id }` |
| 3 | Response mapping | Maps label group response to camelCase |
| 4 | Error | Propagates 404 (novel not found) |
| 5 | Error | Propagates 400 (data too long) |

#### `getLabelGroupById(labelGroupId)`

| # | Category | Test Case |
|---|----------|-----------|
| 1 | Call | Calls `GET /label-groups/{labelGroupId}` |
| 2 | Response mapping | Maps label group from snake_case to camelCase |
| 3 | Error | Propagates 404 (label group not found) |

> **Not yet implemented** — The following backend endpoints do not yet have frontend API functions:
> - `updateLabelGroup` → `PATCH /label-groups/{labelGroupId}`
> - `getLabelDatas` → `GET /label-datas`
> - `getLabelDataById` → `GET /label-datas/{labelDataId}`
> - `getLabelsByLabelData` → `GET /label-datas/{labelDataId}/labels`
> - `createLabelData` → `POST /label-groups/{labelGroupId}/label-datas`
> - `updateLabelDataStream` → `PATCH /label-datas/{labelDataId}`
> - `createLabelDataByAutoLabel` → `POST /label-groups/{labelGroupId}/label-datas/auto-labels`

---

## Relevant Files

- `frontend/vite.config.ts` — Vitest configuration (`test` block)
- `frontend/src/setupTests.ts` — Global test setup
- `frontend/src/api/client.ts` — Axios instance (mocked in tests)
- `frontend/src/api/__test__/` — Test files
- `frontend/src/types/` — TypeScript type definitions

## See Also

- [testing.md](testing.md) — Backend testing guide
- [conventions.md](conventions.md) — Naming conventions and API layer patterns
- [api-design.md](api-design.md) — REST API design decisions
