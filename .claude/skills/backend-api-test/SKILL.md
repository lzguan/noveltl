---
name: backend-api-test
description: Write backend router-level API tests using FastAPI TestClient. Use when writing endpoint tests that verify HTTP status codes, request/response shapes, auth requirements, and error handling.
---

# Backend API Test Skill

Write router-level API tests that exercise FastAPI endpoints via `TestClient`. These tests hit the full request pipeline (router → service → DB) with a real test database.

## Reference Files

Always read these first:
- `docs/backend-testing.md` — testing conventions and patterns
- `docs/conventions.md` — naming conventions
- `docs/api-design.md` — endpoint contracts

## Test Location

Tests go in `backend/tests/{service}/test_{service}_endpoints_{category}.py`

Categories: `basic` (happy path CRUD), `permissions` (access control), `errors` (edge cases and error responses).

## Setup Pattern

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.models import User
# Import other models as needed for fixtures


class TestEndpointName:
    """Tests for {METHOD} {URL_PATH}."""

    def test_happy_path(
        self,
        client: TestClient,
        test_db: Session,
        # fixtures that populate test data
    ):
        response = client.get("/endpoint", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        # Assert response shape matches schema
```

## Key Patterns

### Authentication
```python
# Get a token for a user
from src.auth.service import create_access_token

def get_auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}

# Endpoints with get_current_user require auth
response = client.get("/endpoint", headers=get_auth_header(user))

# Endpoints with get_optional_user work without auth too
response = client.get("/endpoint")  # guest access
```

### Request bodies
```python
# POST with JSON body — use snake_case keys (backend convention)
response = client.post("/novels", json={
    "novel_title": "Test",
    "novel_visibility": "public",
    "novel_type": "original",
    "language_code": "en"
}, headers=get_auth_header(user))
```

### Query parameters
```python
# Query params use kebab-case aliases
response = client.get("/chapters", params={"novel-id": str(novel_id)})
```

### Error responses
```python
def test_not_found_returns_404(self, client, ...):
    response = client.get(f"/novels/{uuid4()}", headers=get_auth_header(user))
    assert response.status_code == 404

def test_unauthorized_returns_401(self, client, ...):
    response = client.patch(f"/novels/{novel_id}", json={...})
    assert response.status_code == 401  # no auth header
```

### Permission tests
```python
def test_guest_cannot_see_private_novel(self, client, private_novel):
    response = client.get(f"/novels/{private_novel.novel_id}")
    assert response.status_code == 404  # zero-knowledge: 404 not 403

def test_contributor_can_edit(self, client, novel, editor_user):
    response = client.patch(
        f"/novels/{novel.novel_id}",
        json={"novel_title": "Updated"},
        headers=get_auth_header(editor_user)
    )
    assert response.status_code == 200
```

## What to test for each endpoint

For every endpoint, write tests covering:

1. **Happy path** — correct status code and response shape
2. **Auth requirement** — 401 if auth required and no token provided
3. **Not found** — 404 for non-existent resource IDs
4. **Permission denied** — 404 (zero-knowledge) or 401 for unauthorized users
5. **Validation errors** — 422 for malformed request bodies
6. **Conflict/duplicate** — 409 for unique constraint violations
7. **Data too long** — 400 for fields exceeding max length

## Fixture conventions

- Fixtures live in `tests/fixtures/populators/{name}.py`
- Fixture names are prefixed with a populator prefix (e.g., `p1_`, `sample_`)
- Fixtures that create DB objects must take `test_db: Session` and commit
- Fixtures must use `NovelContributor` (not `Contributor`) for the current schema
- Register new fixture files in `tests/conftest.py` under `pytest_plugins`

## Naming conventions

- Test classes: `TestRead{Resource}`, `TestCreate{Resource}`, `TestUpdate{Resource}`, `TestDelete{Resource}`
- Test functions: `test_{what_it_verifies}` (e.g., `test_guest_sees_public_and_unlisted`)
- File names: `test_{service}_endpoints_{category}.py`
