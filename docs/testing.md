# Testing Guide

**Last Updated**: March 5, 2026  
**Status**: Draft

This document describes the testing framework and conventions for the NovelTL project.

## Overview

We use **pytest** for all backend tests. The test suite includes:
- Unit tests for service functions
- Integration tests for API endpoints
- Worker tests for background jobs (using monkeypatching)
- Fixture-based database population

## Running Tests

### All Tests

```bash
pytest backend/tests
```

### Specific Test File

```bash
pytest backend/tests/auth/test_auth.py
```

### With Coverage

```bash
pytest --cov=backend/src --cov-report=html backend/tests
```

### By Marker

```bash
# Run only slow tests (e.g., worker integration tests)
pytest -m slow

# Skip slow tests (for quick CI runs)
pytest -m "not slow"

# Run only implementation-focused tests
pytest -m implementation
```

## Test Structure

```
backend/tests/
├── conftest.py              # Shared fixtures (db, client, redis, worker)
├── fixtures/                # Data population fixtures
│   ├── populators/
│   │   ├── sample.py        # Basic test data
│   │   ├── chinese_xianxia_small_test.py  # Novel fixture
│   │   ├── permissions_one.py
│   │   └── score_filter_simple.py
│   ├── password_hash.py     # Password hashing fixture
│   └── filters.py           # Filter-specific fixtures
├── auth/                    # Authentication tests
├── autolabels/              # AutoLabel service tests
├── filters/                 # Filter system tests
├── labels/                  # Label management tests
├── languages/               # Language service tests
├── novels/                  # Novel management tests
├── demos/                   # Learning examples (monkeypatching)
└── test_data/               # Sample text files
```

## Core Fixtures

Defined in `backend/tests/conftest.py`:

### Database Fixtures

```python
@pytest.fixture
def test_db(test_engine, testing_session_local):
    """Creates a fresh test database for each test function."""
    # Drops and recreates all tables
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
```

**Usage:**

```python
def test_create_user(test_db):
    user = User(username="alice", email="alice@example.com")
    test_db.add(user)
    test_db.commit()
    assert user.user_id is not None
```

### Client Fixture

```python
@pytest.fixture
def client(test_db, redis):
    """FastAPI TestClient with overridden dependencies."""
    def override_get_db():
        yield test_db
    def override_get_redis_for_app():
        return redis
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_for_app] = override_get_redis_for_app
    
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

**Usage:**

```python
def test_login(client):
    response = client.post("/token", data={
        "username": "admin",
        "password": "admin"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### Redis Fixture

```python
@pytest.fixture
async def redis():
    """ARQ Redis pool for testing (database=1)."""
    pool = await create_pool(RedisSettings(host='redis', port=6379, database=1))
    yield pool
    await pool.aclose()
```

### Worker Mock Fixture

```python
@pytest.fixture
async def worker_mock(test_url, monkeypatch, redis):
    """Worker configured to use test database via monkeypatching."""
    import src.autolabels.worker.tasks as worker_cfg
    # Monkeypatch worker's SessionLocal to use test database
    monkeypatch.setattr(worker_cfg, 'SessionLocal', 
                        sessionmaker(create_engine(test_url)))
    
    return Worker(
        functions=WorkerSettings.functions,
        redis_pool=redis,
        on_startup=WorkerSettings.on_startup,
        burst=True,      # Run tasks immediately, don't poll
        poll_delay=0
    )
```

**Usage:**

```python
@pytest.mark.asyncio
async def test_autolabel_worker(client, test_db, worker_mock):
    # Enqueue job via API
    response = client.post("/auto-labels/", json={
        "raw_chapter_revision_ids": [1, 2, 3]
    })
    
    # Run worker in burst mode (processes all tasks then exits)
    await worker_mock.async_run()
    
    # Check results in database
    auto_label = test_db.query(AutoLabel).first()
    assert auto_label is not None
```

## Test Markers

Define markers in `pytest.ini`:

```ini
[pytest]
markers =
    slow: Tests that take >1 second (e.g., worker integration tests)
    implementation: Tests verifying internal implementation details
```

**Usage:**

```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_autolabel_large_batch(worker_mock, test_db):
    # Process 100 chapters
    ...

@pytest.mark.implementation
def test_service_layer_internal_logic():
    # Test private function behavior
    ...
```

## Monkeypatching for Worker Tests

**Challenge:** The worker process runs in isolation and creates its own database connection. In tests, we need the worker to use the test database instead of the production database.

**Solution:** Use `pytest.MonkeyPatch` to override the worker's `SessionLocal` import before it creates connections.

### How It Works

1. **Worker normally does this:**
   ```python
   # src/autolabels/worker/tasks.py
   from src.autolabels.worker.config import SessionLocal
   
   async def infer_autolabels(job_id):
       db = SessionLocal()  # Connects to production db
       ...
   ```

2. **Test overrides SessionLocal:**
   ```python
   # conftest.py
   import src.autolabels.worker.tasks as worker_cfg
   monkeypatch.setattr(worker_cfg, 'SessionLocal', 
                       sessionmaker(create_engine(test_url)))
   ```

3. **Now worker uses test database:**
   ```python
   db = SessionLocal()  # Now connects to test_db!
   ```

**Key Insight:** Monkeypatching works at the module namespace level. We patch the *imported reference* in the worker module, not the original definition.

For detailed explanation and examples, see [concepts/monkeypatching.md](concepts/monkeypatching.md).

## Data Fixtures

### Sample Fixture

Minimal data for basic tests:

```python
@pytest.fixture
def sample_data(test_db):
    admin = User(username="admin", email="admin@example.com")
    test_db.add(admin)
    test_db.commit()
    return {"admin": admin}
```

### Chinese Xianxia Small Test

Realistic novel data:

```python
@pytest.fixture
def chinese_xianxia_small_test(test_db):
    # Creates novel with chapters, revisions, labels
    novel = Novel(...)
    chapters = [RawChapter(...) for _ in range(10)]
    # ... populate labels, autolabels
    test_db.add_all([novel] + chapters)
    test_db.commit()
    return {"novel": novel, "chapters": chapters}
```

### Score Filter Simple

Data for filter tests:

```python
@pytest.fixture
def score_filter_simple(test_db):
    # Labels with varying scores for ScoreFilter testing
    labels = [
        Label(word="他", score=0.5),
        Label(word="张三", score=0.95),
        Label(word="的", score=0.3),
    ]
    test_db.add_all(labels)
    test_db.commit()
    return labels
```

## Writing Tests

### Service Tests

Test business logic in service layer:

```python
from src.labels.service import insert_label_group

def test_insert_label_group(test_db, sample_data):
    admin = sample_data["admin"]
    
    label_group = insert_label_group(
        db=test_db,
        current_user=admin,
        raw_chapter_revision_id=1,
        entity_group="PER"
    )
    
    assert label_group.label_group_id is not None
    assert label_group.entity_group == "PER"
```

### Router Tests

Test API endpoints:

```python
def test_create_novel(client, sample_data):
    response = client.post("/novels/", json={
        "novel_title": "My Novel",
        "original_language_id": 1
    }, headers={"Authorization": f"Bearer {get_token(client)}"})
    
    assert response.status_code == 201
    data = response.json()
    assert data["novel_title"] == "My Novel"
```

### Filter Tests

Test filter phases:

```python
from src.filters.score_filter import ScoreFilter

def test_score_filter_flag_phase(test_db, score_filter_simple):
    filter = ScoreFilter()
    
    instances = filter.flag_instances(
        db=test_db,
        current_user=None,
        options=ScoreFlagOptions(min_score=0.8, ...)
    )
    
    # Should only flag labels with score < 0.8
    assert len(instances) == 2  # "他" (0.5) and "的" (0.3)
    assert all(inst.score < 0.8 for inst in instances)
```

### Worker Tests

Test background jobs:

```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_autolabel_state_transitions(client, test_db, worker_mock):
    # Create autolabel job
    response = client.post("/auto-labels/", json={
        "raw_chapter_revision_ids": [1]
    })
    auto_label_id = response.json()["auto_label_id"]
    
    # Initially PENDING
    auto_label = test_db.get(AutoLabel, auto_label_id)
    assert auto_label.status == "PENDING"
    
    # Run worker
    await worker_mock.async_run()
    
    # Should transition to DONE
    test_db.refresh(auto_label)
    assert auto_label.status == "DONE"
    assert auto_label.completion_timestamp is not None
```

## Best Practices

### Test Isolation

- Each test gets a fresh database (`test_db` fixture drops/recreates tables)
- Use `scope="function"` for fixtures that modify state
- Clear dependency overrides after tests

### Avoid Redundant Tests

- Don't test framework behavior (e.g., SQLAlchemy's ORM)
- Don't test library functions (e.g., bcrypt's hashing)
- Focus on business logic and integration points

### Use Fixtures for Setup

**Bad:**

```python
def test_something(test_db):
    user = User(username="alice")
    test_db.add(user)
    test_db.commit()
    novel = Novel(novel_title="Test", owner_id=user.user_id)
    test_db.add(novel)
    test_db.commit()
    # ...actual test...
```

**Good:**

```python
@pytest.fixture
def user_with_novel(test_db):
    user = User(username="alice")
    test_db.add(user)
    test_db.commit()
    novel = Novel(novel_title="Test", owner_id=user.user_id)
    test_db.add(novel)
    test_db.commit()
    return {"user": user, "novel": novel}

def test_something(user_with_novel):
    novel = user_with_novel["novel"]
    # ...actual test...
```

### Mark Slow Tests

```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_process_100_chapters(worker_mock):
    # Long-running test
    ...
```

Then skip in development:

```bash
pytest -m "not slow"
```

## Coverage

Aim for >80% coverage on:
- Service layer
- Router layer
- Filter implementations
- Permission checks

Less emphasis on:
- Models (mostly ORM boilerplate)
- Schemas (Pydantic handles validation)
- Config files

## Continuous Integration (Not implemented yet)

Run in CI pipeline:

```yaml
- name: Run tests
  run: |
    docker-compose -f compose.test.yaml up -d
    docker-compose exec backend pytest --cov=src --cov-report=xml
    docker-compose down
```

## Debugging Tests

### Print Database State

```python
def test_something(test_db):
    # ... test code ...
    
    # Debug: print all users
    users = test_db.query(User).all()
    for user in users:
        print(f"User: {user.username} (ID: {user.user_id})")
```

### Interactive Debugging

```python
def test_something(test_db):
    import pdb; pdb.set_trace()  # Breakpoint
    # Step through test interactively
```

### Check SQL Queries

```python
from sqlalchemy import event

# Log all SQL queries
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

## Common Pitfalls

### Forgetting to Commit

```python
# Bad: Data not persisted
test_db.add(user)
# test continues without commit...

# Good:
test_db.add(user)
test_db.commit()
```

### Reusing Database Objects Across Tests

```python
# Bad: `user` from test_db in one test may not exist in another
user = test_db.query(User).first()

# Good: Create fresh data via fixtures
```

### Not Awaiting Async Functions

```python
# Bad:
worker_mock.async_run()  # Returns coroutine, doesn't execute!

# Good:
await worker_mock.async_run()
```

## Relevant Files

- `backend/tests/conftest.py` - Shared fixtures
- `backend/tests/fixtures/` - Data population fixtures
- `backend/pytest.ini` - Pytest configuration
- `backend/tests/demos/monkeypatching/` - Monkeypatching examples
- `docs/concepts/monkeypatching.md` - Detailed monkeypatching guide

## See Also

- [concepts/monkeypatching.md](concepts/monkeypatching.md) - Worker testing deep dive
- [background-jobs.md](background-jobs.md) - AutoLabel worker system
- [api-design.md](api-design.md) - API endpoint patterns and error handling
- [conventions.md](conventions.md) - Code conventions
- [architecture.md](architecture.md) - System architecture
