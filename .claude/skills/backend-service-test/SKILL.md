---
name: backend-service-test
description: Write backend service-level unit tests that exercise service functions directly with a real DB session. Use when testing business logic, permission helpers, error handling, and query behavior.
---

# Backend Service Test Skill

Write service-level tests that call service functions directly with a real database session. These tests verify business logic, permission enforcement, and error handling without going through the HTTP layer.

## Reference Files

Always read these first:
- `docs/backend-testing.md` — testing conventions
- `docs/permissions.md` — permission model and helper patterns
- `docs/conventions.md` — naming conventions

## Test Location

Tests go in `backend/tests/{service}/test_{service}_service_{category}.py`

Categories: `permissions` (permission helper behavior), `basic` (CRUD operations), `errors` (edge cases).

## Setup Pattern

```python
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.novels.models import Novel, Chapter, ChapterContent
from src.novels.service import query_novel_by_id, insert_chapter
from src.novels.exceptions import NovelNotFoundException
from src.exceptions import InsufficientPermissionsException


class TestQueryNovelById:

    def test_returns_novel_for_contributor(
        self, test_db: Session, novel: Novel, contributor_user: User
    ):
        result = query_novel_by_id(test_db, contributor_user, novel.novel_id)
        assert result.novel_id == novel.novel_id

    def test_raises_not_found_for_guest_on_private(
        self, test_db: Session, private_novel: Novel
    ):
        with pytest.raises(NovelNotFoundException):
            query_novel_by_id(test_db, None, private_novel.novel_id)
```

## Permission helper tests

Test permission helpers directly by applying them to raw SQLAlchemy statements:

```python
from src.novels.permissions import novel_mod_access_select

class TestNovelModAccessSelect:

    def test_guest_sees_public_and_unlisted(
        self, test_db: Session,
        public_novel: Novel,
        unlisted_novel: Novel,
        private_novel: Novel,
    ):
        q = select(Novel)
        q = novel_mod_access_select(q, None)
        results = test_db.execute(q).scalars().all()
        ids = {n.novel_id for n in results}
        assert public_novel.novel_id in ids
        assert unlisted_novel.novel_id in ids
        assert private_novel.novel_id not in ids

    def test_admin_sees_all(
        self, test_db: Session, admin: User,
        public_novel: Novel, private_novel: Novel,
    ):
        q = select(Novel)
        q = novel_mod_access_select(q, admin)
        results = test_db.execute(q).scalars().all()
        ids = {n.novel_id for n in results}
        assert public_novel.novel_id in ids
        assert private_novel.novel_id in ids
```

## Key patterns

### Testing insert-from-select with permissions
```python
def test_editor_can_insert_chapter(
    self, test_db: Session, editor_user: User, novel: Novel
):
    request = schemas.CreateChapter(chapter_num=1)
    chapter = insert_chapter(test_db, editor_user, novel.novel_id, request)
    assert chapter.chapter_num == 1
    assert chapter.novel_id == novel.novel_id

def test_viewer_cannot_insert_chapter(
    self, test_db: Session, viewer_user: User, novel: Novel
):
    request = schemas.CreateChapter(chapter_num=1)
    with pytest.raises(InsufficientPermissionsException):
        insert_chapter(test_db, viewer_user, novel.novel_id, request)
```

### Testing error handling
```python
def test_duplicate_chapter_num_raises(
    self, test_db: Session, user: User, novel: Novel
):
    insert_chapter(test_db, user, novel.novel_id, schemas.CreateChapter(chapter_num=1))
    with pytest.raises(ChapterNumDuplicateException):
        insert_chapter(test_db, user, novel.novel_id, schemas.CreateChapter(chapter_num=1))
```

### Testing cross-service interactions
```python
def test_label_data_requires_chapter_content_access(
    self, test_db: Session, user: User, label_group: LabelGroup,
    private_chapter_content: ChapterContent
):
    """User has label group access but NOT chapter content access."""
    with pytest.raises(LabelGroupNotFoundException):
        insert_label_data(test_db, user, label_group.label_group_id,
            schemas.CreateLabelData(chapter_content_id=private_chapter_content.chapter_content_id))
```

## User role matrix

Every permission-sensitive function should be tested with:

| Role | Expected behavior |
|------|-------------------|
| `None` (guest) | See public/unlisted only, cannot mutate |
| Regular user (non-contributor) | Same as guest for that resource |
| Viewer contributor | Can read, cannot mutate |
| Editor contributor | Can read and mutate |
| Owner contributor | Full control including delete |
| Admin | Bypasses all checks |

## Fixture conventions

Same as backend-api-test skill:
- Fixtures in `tests/fixtures/populators/{name}.py`
- Prefixed names, take `test_db: Session`, commit after adding
- Register in `tests/conftest.py` `pytest_plugins`

## Naming conventions

- Test classes: `Test{FunctionName}` (e.g., `TestQueryNovelById`, `TestInsertChapter`)
- Test functions: `test_{scenario}` (e.g., `test_guest_cannot_see_private`)
- File names: `test_{service}_service_{category}.py`
