# API Design Guide

**Last Updated**: March 5, 2026  
**Status**: Draft

This document describes the REST API design patterns, conventions, and standards for the NovelTL backend.

## Naming Convention Summary

**Critical Rule**: Different casing for different contexts:

- **URL Paths**: `kebab-case` → `/auto-labels/{id}`, `/label-groups/{id}`, `/raw-chapters/{id}`
- **JSON Fields**: `snake_case` → `{"novel_title": "...", "label_group_name": "..."}`
- **Query Params**: `snake_case` → `?title_contains=example&is_public=true`
- **Python Code**: `snake_case` → Functions, variables, schema fields

This split convention keeps URLs readable (kebab-case is web standard) while maintaining consistency between JSON bodies and Python backend code (both use snake_case).

## Overview

The NovelTL API follows RESTful principles using FastAPI. Key characteristics:
- **Resource-oriented URLs** - Nouns, not verbs (e.g., `/novels/{id}`, not `/getNovel`)
- **HTTP methods** - Standard semantics (GET, POST, PUT/PATCH, DELETE)
- **JSON payloads** - All request/response bodies use JSON
- **OAuth2 + JWT** - Bearer token authentication
- **Pydantic validation** - Automatic request/response schema validation

## Authentication

### Token-Based Authentication

**Obtaining a Token**:
```http
POST /token
Content-Type: application/x-www-form-urlencoded

username=alice&password=secret123

Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Using the Token**:
```http
GET /novels/123
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Lifecycle

- **Expiration**: 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Storage**: Client stores in memory or secure storage
- **Refresh**: No refresh tokens yet - re-authenticate after expiry

### Authentication Dependencies

**Optional User** - Endpoint accessible to anonymous users:
```python
@router.get('/novels')
async def read_novels(
    current_user: Annotated[User | None, Depends(get_optional_user)]
):
    # current_user is None for anonymous requests
    # Used for permission filtering (e.g., show only public novels)
```

**Required User** - Endpoint requires authentication:
```python
@router.post('/novels')
async def create_novel(
    current_user: Annotated[User, Depends(get_current_user)]
):
    # Raises 401 if no token or invalid token
    # current_user is guaranteed non-None
```

## URL Design Patterns

### Naming Conventions

**URL Paths**: Use `kebab-case` for multi-word resources:
```
/auto-labels/{auto_label_id}        # kebab-case in path
/label-groups/{label_group_id}      # kebab-case in path
/raw-chapters/{chapter_id}          # kebab-case in path
```

**JSON Bodies**: Use `snake_case` for field names:
```json
{
  "novel_title": "Example",         // snake_case in JSON
  "novel_visibility": "public",    // snake_case in JSON
  "label_group_name": "Characters" // snake_case in JSON
}
```

**Query Parameters**: Use `snake_case` (or camelCase with FastAPI `alias` if frontend prefers):
```
/novels?title_contains=example              # snake_case
/novels/mine?editable=true&title_contains=  # snake_case
```

### Resource Hierarchy

URLs follow parent-child relationships:

```
/novels/{novel_id}                              # Novel resource
/novels/{novel_id}/raw-chapters                 # Chapters belong to novel
/novels/{novel_id}/raw-chapters/{chapter_id}    # Specific chapter

/label-groups/{label_group_id}                  # Label group resource
/label-groups/{label_group_id}/label-data       # Label data for group
```

**Why not `/raw-chapters/{chapter_id}`?**
- Context clarity - chapter belongs to specific novel
- Permission enforcement - easier to check novel access
- Prevents cross-novel chapter access bugs

### Query Parameters

**Filtering**:
```http
GET /novels?title_contains=harry
GET /novels/mine?editable=true&title_contains=potter
```

**Conventions**:
- Use `snake_case` for consistency with JSON bodies
- Boolean flags default to `false`
- Optional filters default to `None` (no filtering)
- Can use FastAPI `alias` for camelCase if frontend strongly prefers it

### Path Parameters

Always integers for IDs:
```python
@router.get('/novels/{novel_id}')
async def read_novel(novel_id: int):
    # FastAPI auto-validates novel_id is integer
    # Returns 422 if non-integer provided
```

## HTTP Methods

### GET - Read Resources

**Single Resource**:
```http
GET /novels/123
Response: 200 OK
{
  "novel_id": 123,
  "novel_title": "Example Novel",
  "novel_visibility": "public",
  ...
}
```

**Collection**:
```http
GET /novels?title_contains=example
Response: 200 OK
[
  {"novel_id": 123, "novel_title": "Example Novel", ...},
  {"novel_id": 456, "novel_title": "Example Story", ...}
]
```

**Error Cases**:
- `404 Not Found` - Resource doesn't exist or insufficient permissions to view
- `401 Unauthorized` - Authentication required but missing/invalid
- `403 Forbidden` - Authenticated but insufficient permissions

### POST - Create Resources

**Standard Creation**:
```http
POST /novels
Content-Type: application/json
Authorization: Bearer <token>

{
  "novel_title": "New Novel",
  "novel_visibility": "private",
  "novel_type": "original",
  "language_code": "en"
}

Response: 201 Created
{
  "novel_id": 789,
  "novel_title": "New Novel",
  ...
}
```

**Nested Resource Creation**:
```http
POST /novels/123/raw-chapters
{
  "raw_chapter_num": 1
}

Response: 201 Created
{
  "raw_chapter_id": 456,
  "raw_chapter_num": 1,
  "novel_id": 123
}
```

**Async Job Creation**:
```http
POST /auto-labels
{
  "novel_id": 123,
  "auto_label_model_name": "uer/roberta-base-finetuned-cluener2020-chinese",
  "auto_label_model_params": {...}
}

Response: 200 OK
{
  "auto_label_ids": [1, 2, 3],
  "auto_label_status": "pending"
}
```

**Error Cases**:
- `400 Bad Request` - Invalid request body syntax
- `422 Unprocessable Entity` - Validation error (Pydantic schema violation)
- `409 Conflict` - Resource already exists (unique constraint violation)
- `404 Not Found` - Parent resource doesn't exist

### PUT/PATCH - Update Resources

**Partial Update (PATCH)** - Preferred:
```http
PATCH /novels/123
{
  "novel_title": "Updated Title"
}

Response: 200 OK
{
  "novel_id": 123,
  "novel_title": "Updated Title",
  "novel_visibility": "public",  # Unchanged fields preserved
  ...
}
```

**Implementation**:
```python
@router.patch('/novels/{novel_id}')
async def update_novel(
    novel_id: int,
    request: schemas.UpdateNovel
):
    # UpdateNovel schema has all fields as Optional
    # model_dump(exclude_unset=True) only includes fields client sent
    updates = request.model_dump(exclude_unset=True)
    novel = service.modify_novel(db, current_user, novel_id, updates)
    return novel
```

**Full Replacement (PUT)** - Not currently used:
```python
# Would require all fields to be provided
# More common in systems with strict resource replacement semantics
```

**Error Cases**:
- `404 Not Found` - Resource doesn't exist or no permission
- `422 Unprocessable Entity` - Validation error
- `409 Conflict` - Update violates constraint

### DELETE - Remove Resources

```http
DELETE /novels/123/raw-chapters/456/revisions/789

Response: 204 No Content
```

**Idempotency**: Multiple DELETE requests to same resource return same status:
- First request: `204 No Content` (success)
- Subsequent requests: `204 No Content` (already deleted, no-op)

**Error Cases**:
- `404 Not Found` - Resource doesn't exist (or no permission to see it existed)
- `409 Conflict` - Cannot delete due to foreign key constraints or business rules

## Request/Response Formats

### Request Body Validation

All requests validated via Pydantic schemas:

```python
class CreateNovel(BaseModel):
    novel_title: str                      # Required
    novel_description: str | None = None  # Optional with default
    novel_visibility: Visibility          # Enum validation
    language_code: str                    # Required
```

**Validation Errors**:
```http
POST /novels
{
  "novel_title": "",  # Empty string violates constraints
  "novel_visibility": "invalid_value"
}

Response: 422 Unprocessable Entity
{
  "detail": [
    {
      "loc": ["body", "novel_title"],
      "msg": "String should have at least 1 character",
      "type": "string_too_short"
    },
    {
      "loc": ["body", "novel_visibility"],
      "msg": "Input should be 'public', 'private', or 'protected'",
      "type": "enum"
    }
  ]
}
```

### Response Body Standards

**Single Resource**:
```python
@router.get('/novels/{novel_id}', response_model=schemas.Novel)
async def read_novel(novel_id: int):
    return service.query_novel_by_id(db, current_user, novel_id)
```

Returns exact schema shape - FastAPI serializes ORM models via `from_attributes=True`.

**Collection**:
```python
@router.get('/novels', response_model=list[schemas.Novel])
async def read_novels():
    return service.query_novels_by_title(db, current_user, title_contains)
```

**No Content**:
```python
@router.delete('/novels/{novel_id}', status_code=204)
async def delete_novel(novel_id: int):
    service.remove_novel(db, current_user, novel_id)
    # No return value - FastAPI returns empty response with 204
```

### Metadata vs Full Resource

**Optimization Pattern**: Separate endpoints for metadata vs full data:

```python
# Full resource with large text field
class RawChapterRevision(BaseModel):
    raw_chapter_revision_id: int
    raw_chapter_revision_text: str  # Could be 100KB+
    ...

# Metadata only (for list endpoints)
class RawChapterRevisionMeta(BaseModel):
    raw_chapter_revision_id: int
    raw_chapter_revision_title: str
    # No text field - much smaller payload
    
@router.get('/raw-chapters/{chapter_id}/revisions', 
            response_model=list[RawChapterRevisionMeta])
async def list_revisions():
    # Returns metadata only - fast for large lists
    
@router.get('/revisions/{revision_id}',
            response_model=RawChapterRevision)
async def get_revision():
    # Returns full revision with text - slower but necessary for detail view
```

## Error Handling

### HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| `200` | OK | Successful GET, PATCH, or async POST |
| `201` | Created | Successful POST creating new resource |
| `204` | No Content | Successful DELETE |
| `400` | Bad Request | Malformed request (invalid JSON) |
| `401` | Unauthorized | Missing or invalid authentication token |
| `403` | Forbidden | Authenticated but insufficient permissions |
| `404` | Not Found | Resource doesn't exist (or no permission) |
| `409` | Conflict | Unique constraint violation, business rule violation |
| `422` | Unprocessable Entity | Valid JSON but fails Pydantic validation |
| `500` | Internal Server Error | Unexpected server error |

### Exception Mapping

**Service Layer Exceptions → HTTP Responses**:

```python
# In service layer
if not novel:
    raise NovelNotFoundException(f"Novel {novel_id} not found")

# In router
try:
    novel = service.query_novel_by_id(db, current_user, novel_id)
except NovelNotFoundException as e:
    raise HTTPException(status_code=404, detail=str(e))
```

**Common Patterns**:

```python
# 404 - Not Found
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Novel not found."
)

# 401 - Unauthorized
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"}
)

# 403 - Forbidden
raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Insufficient permissions to access this resource"
)

# 409 - Conflict
raise HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="A chapter with this number already exists for this novel"
)
```

### Error Response Format

FastAPI standard error format:

```json
{
  "detail": "Novel not found."
}
```

For validation errors (422):

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Error message",
      "type": "error_type"
    }
  ]
}
```

### Information Disclosure Prevention

**Problem**: Returning different errors for "not found" vs "no permission" reveals resource existence.

**Solution**: Return 404 for both cases:

```python
def query_novel_by_id(db, current_user, novel_id) -> models.Novel:
    stmt = select(models.Novel).where(Novel.novel_id == novel_id)
    stmt = novel_view_access_select(stmt, current_user)  # Filters by permissions
    
    result = db.execute(stmt).scalar_one_or_none()
    if not result:
        # Could be: (1) doesn't exist, (2) no permission
        # Both raise same exception to prevent enumeration
        raise NovelNotFoundException(f"Novel {novel_id} not found")
    
    return result
```

From client perspective:
- Novel doesn't exist → 404
- Novel exists but no permission → 404
- Cannot distinguish → prevents information leakage

## API Versioning

**Current Status**: No versioning yet (v1 implicit)

**Future Approach** (when breaking changes needed):

Option 1 - URL Prefix:
```
/v1/novels/{novel_id}
/v2/novels/{novel_id}
```

Option 2 - Header-Based:
```http
GET /novels/123
Accept: application/vnd.noveltl.v2+json
```

**Recommendation**: URL prefix for simplicity and discoverability.

## OpenAPI Documentation

FastAPI auto-generates OpenAPI schema at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### Enhancing Documentation

**Route Descriptions**:
```python
@router.get(
    '/novels/{novel_id}',
    response_model=schemas.Novel,
    summary="Get novel by ID",
    description="Retrieves a single novel by its unique identifier. Returns 404 if the novel doesn't exist or the user lacks permission to view it.",
    response_description="The requested novel",
    responses={
        404: {"description": "Novel not found or insufficient permissions"},
        401: {"description": "Authentication required"}
    }
)
async def read_novel(novel_id: int):
    ...
```

**Schema Descriptions**:
```python
class Novel(BaseModel):
    """
    Represents a novel in the NovelTL system.
    
    Novels can be originals, translations, or other types. Access is controlled
    by visibility level and contributor permissions.
    """
    novel_id: int = Field(description="Unique identifier for the novel")
    novel_title: str = Field(description="Title of the novel", max_length=255)
    novel_visibility: Visibility = Field(description="Who can view this novel")
```

## Performance Considerations

### N+1 Query Prevention

**Problem**:
```python
# BAD: N+1 queries
@router.get('/novels', response_model=list[NovelWithChapters])
async def read_novels():
    novels = db.query(Novel).all()  # 1 query
    for novel in novels:
        novel.chapters  # N queries (lazy loading)
    return novels
```

**Solution**: Eager loading with `joinedload`:
```python
# GOOD: 1 query
@router.get('/novels', response_model=list[NovelWithChapters])
async def read_novels():
    stmt = select(Novel).options(joinedload(Novel.chapters))
    novels = db.execute(stmt).unique().scalars().all()
    return novels
```

### Pagination

**TODO**: Not yet implemented (see [issues.md](issues.md))

**Planned Pattern**:
```python
@router.get('/novels')
async def read_novels(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    stmt = select(Novel).limit(limit).offset(offset)
    novels = db.execute(stmt).scalars().all()
    return novels
```

### Response Size Optimization

Use metadata schemas for list endpoints:
```python
# List endpoint - metadata only
@router.get('/chapters/{chapter_id}/revisions',
            response_model=list[RawChapterRevisionMeta])

# Detail endpoint - full data
@router.get('/revisions/{revision_id}',
            response_model=RawChapterRevision)
```

## Security Best Practices

### Input Validation

**Always through Pydantic schemas** - Never trust raw input:
```python
# GOOD
@router.post('/novels')
async def create_novel(request: schemas.CreateNovel):
    # request is fully validated by Pydantic
    
# BAD
@router.post('/novels')
async def create_novel(request: dict):
    # No validation - vulnerable to injection, type errors
```

### SQL Injection Prevention

**Use SQLAlchemy ORM** - Parameterized queries by default:
```python
# GOOD - SQLAlchemy escapes parameters
stmt = select(Novel).where(Novel.novel_title == user_input)

# BAD - Raw SQL with string interpolation (DON'T DO THIS)
query = f"SELECT * FROM novels WHERE title = '{user_input}'"
```

### Authorization Checks

**Every endpoint** must verify permissions:
```python
@router.delete('/novels/{novel_id}')
async def delete_novel(
    novel_id: int,
    current_user: Annotated[User, Depends(get_current_user)]
):
    # Service layer checks permissions via novel_mod_access_delete()
    service.remove_novel(db, current_user, novel_id)
```

See [permissions.md](permissions.md) for detailed permission patterns.

## Relevant Files

- `backend/src/*/router.py` - API endpoint definitions
- `backend/src/*/schemas.py` - Request/response Pydantic models
- `backend/src/*/service.py` - Business logic and database operations
- `backend/src/auth/dependencies.py` - Authentication dependencies (`get_current_user`, `get_optional_user`)
- `backend/src/auth/utils.py` - JWT token creation and verification
- `backend/src/database.py` - Database session management
- `backend/src/main.py` - FastAPI app initialization, router registration

## See Also

- [architecture.md](architecture.md) - Overall system architecture
- [permissions.md](permissions.md) - Access control and permission helpers
- [database-schema.md](database-schema.md) - Database models referenced in schemas
- [conventions.md](conventions.md) - Naming conventions for routes and schemas
- [testing.md](testing.md) - API endpoint testing strategies
