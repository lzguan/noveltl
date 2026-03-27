# API Design Guide

**Last Updated**: March 20, 2026  
**Status**: Complete

This document covers the project-specific API design decisions for the NovelTL backend. For standard REST/FastAPI patterns (HTTP methods, Pydantic validation, error response format), see the auto-generated OpenAPI docs at `http://localhost:8000/docs`.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Naming Conventions](#naming-conventions)
3. [Resource Hierarchy](#resource-hierarchy)
4. [Metadata vs Full Resource](#metadata-vs-full-resource)
5. [Information Disclosure Prevention](#information-disclosure-prevention)

---

## Authentication

### Token Lifecycle

- **Endpoint**: `POST /token` (form-encoded `username` + `password`)
- **Response**: `{"access_token": "...", "token_type": "bearer"}`
- **Expiration**: 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Refresh tokens**: Not implemented — client must re-authenticate after expiry (see [GitHub Issues](https://github.com/lzguan/NovelTL_Dev/issues))

### Authentication Dependencies

Two FastAPI dependencies control per-endpoint auth requirements:

| Dependency | Type | When to use |
|-----------|------|-------------|
| `get_current_user` | `User` | Endpoint requires authentication. Returns 401 if token missing/invalid. |
| `get_optional_user` | `User \| None` | Endpoint accessible to anonymous users. `None` means no token. Used with permission helpers to filter visible resources. |

```python
# Anonymous-accessible — permission helpers filter results based on whether user is None
@router.get('/novels')
async def read_novels(
    current_user: Annotated[User | None, Depends(get_optional_user)]
): ...

# Auth-required — 401 if no valid token
@router.post('/novels')
async def create_novel(
    current_user: Annotated[User, Depends(get_current_user)]
): ...
```

## Naming Conventions

URLs use `kebab-case` (web standard), JSON bodies and Python code use `snake_case`. This keeps URLs readable while maintaining consistency between payload fields and backend code. See [conventions.md](conventions.md) for the full naming rules.

| Context | Casing | Examples |
|---------|--------|----------|
| URL paths | `kebab-case` | `/auto-labels/{id}`, `/label-groups/{id}` |
| JSON fields | `snake_case` | `novel_title`, `label_group_name` |
| Query params | `kebab-case` aliases | `?title-contains=example`, `?is-public=true` |
| Path params | `snake_case` | `{novel_id}`, `{chapter_id}` |

Multi-word query params use FastAPI's `Query(alias="kebab-name")`. Single-word params like `start`, `end`, `editable` need no alias.

## Resource Hierarchy

**Every individual resource has exactly one canonical URI** (`/{resource-type}/{id}`). There are no alternative paths to the same resource.

Nested paths exist only for two purposes:
- **Creation** — `POST /parent/{id}/child` establishes the parent relationship
- **Scoped collection queries** — `GET /parent/{id}/children` returns children filtered to a parent

Direct read/update/delete always go through the flat `/{resource}/{id}` path, never through a nested one.

For the full route listing, see OpenAPI at `http://localhost:8000/docs`.

## Metadata vs Full Resource

Resources with large payloads (e.g., chapter revision text can be 100KB+) have two schemas:

| Schema | Used by | Includes large fields |
|--------|---------|----------------------|
| `Revision` | `GET /revisions/{id}` | Yes (`revision_text`) |
| `RevisionMeta` | `GET /chapters/{id}/revisions`, `GET /novels/{id}/revisions` | No |

Same pattern applies to `AutoLabel` (full, includes `auto_label_data` JSONB) vs `AutoLabelMeta` (list endpoints, no inference data).

## Information Disclosure Prevention

Query endpoints return 404 for both "resource doesn't exist" and "resource exists but user lacks permission." The permission helpers (`*_mod_access_select`) filter at the query level, so the service layer never distinguishes between the two cases:

```python
def query_novel_by_id(db, current_user, novel_id):
    stmt = select(Novel).where(Novel.novel_id == novel_id)
    stmt = novel_mod_access_select(stmt, current_user)  # Filters by permissions
    result = db.execute(stmt).scalar_one_or_none()
    if not result:
        raise NovelNotFoundException(...)  # Could be missing OR forbidden
```

This prevents resource enumeration — a client cannot probe whether a private novel ID exists.

## Relevant Files

- `backend/src/*/router.py` - Endpoint definitions
- `backend/src/*/schemas.py` - Pydantic request/response models
- `backend/src/*/service.py` - Business logic
- `backend/src/auth/dependencies.py` - `get_current_user`, `get_optional_user`
- `backend/src/auth/utils.py` - JWT creation and verification
- `backend/src/main.py` - Router registration

## See Also

- [architecture.md](architecture.md) - System architecture
- [permissions.md](permissions.md) - Permission helpers referenced above
- [database-schema.md](database-schema.md) - Database models
- [conventions.md](conventions.md) - Full naming conventions
- [backend-testing.md](backend-testing.md) - API testing strategies
