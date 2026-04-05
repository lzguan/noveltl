---
name: integration-test
description: Write full-stack integration tests that verify end-to-end workflows. Use for multi-step scenarios (create novel → add chapter → add content → label it) and cross-service interactions.
---

# Integration Test Skill

Write integration tests that exercise complete user workflows across multiple services. These tests verify that the full stack works together correctly, not just individual endpoints or functions.

## When to use integration tests vs unit tests

| Use integration tests for | Use unit tests for |
|---|---|
| Multi-step workflows (create → edit → label → filter) | Single function behavior |
| Cross-service interactions (novel + labels + autolabels) | Permission helper logic |
| Data consistency after complex operations | Individual error cases |
| Race condition scenarios | Request/response shape validation |

## Test Location

`backend/tests/integration/test_{workflow_name}.py`

## Setup

Integration tests use the same fixtures as other backend tests (`test_db`, `client`, etc.) but exercise longer sequences:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.auth.service import create_access_token
from src.auth.models import User


class TestNovelLabelingWorkflow:
    """End-to-end: create novel → add chapter → add content → create label group → auto-label → apply labels."""

    def test_full_labeling_pipeline(
        self,
        client: TestClient,
        test_db: Session,
        sample_users: list[User],
        sample_languages: dict,
    ):
        user = sample_users[1]  # regular user
        headers = {"Authorization": f"Bearer {create_access_token(user)}"}

        # Step 1: Create novel
        resp = client.post("/novels", json={
            "novel_title": "Integration Test Novel",
            "novel_visibility": "public",
            "novel_type": "original",
            "language_code": "en",
        }, headers=headers)
        assert resp.status_code == 200
        novel_id = resp.json()["novel_id"]

        # Step 2: Create chapter
        resp = client.post(f"/novels/{novel_id}/chapters", json={
            "chapter_num": 1,
        }, headers=headers)
        assert resp.status_code == 200
        chapter_id = resp.json()["chapter_id"]

        # Step 3: Add content via text operations
        # ... (get chapter content, apply text ops)

        # Step 4: Create label group
        resp = client.post("/label-groups", json={
            "label_group_name": "Test Labels",
            "novel_id": str(novel_id),
        }, headers=headers)
        assert resp.status_code == 200
        label_group_id = resp.json()["label_group_id"]

        # Step 5: Verify cross-service access
        # The label group should be accessible because user owns the novel
        resp = client.get(f"/label-groups/{label_group_id}", headers=headers)
        assert resp.status_code == 200
```

## Workflow categories to test

### 1. Content creation workflow
- Create source work → create novel under it → add chapters → add content → verify hierarchy

### 2. Labeling workflow
- Create label group → create label data for chapter content → add/update/delete labels → verify overlap constraints

### 3. Auto-labeling workflow
- Create content → request auto-labels → verify status transitions (PENDING → PROCESSING → DONE) → apply auto-labels to label group

### 4. Permission boundary workflows
- User A creates novel → User B cannot edit → User A adds User B as editor → User B can now edit
- Novel visibility change from public → private → verify labels from other users still work but novel is hidden

### 5. Text editing with label migration
- Create content with labels → apply text operations → verify labels migrate to new content version with correct positions

### 6. Filter workflow
- Create labels with various scores → flag low-score instances → get contexts → decide → apply filter → verify labels removed

## Multi-user scenarios

```python
def test_contributor_role_escalation(self, client, test_db, ...):
    """Viewer gets upgraded to editor and can now modify."""
    # As viewer: try to edit → should fail
    resp = client.patch(f"/novels/{novel_id}", json={...}, headers=viewer_headers)
    assert resp.status_code == 401

    # Admin upgrades viewer to editor
    # ... (add contributor with editor role)

    # As editor: edit → should succeed
    resp = client.patch(f"/novels/{novel_id}", json={...}, headers=viewer_headers)
    assert resp.status_code == 200
```

## Future: Playwright E2E tests

When frontend E2E tests are added:
- Tests will live in `frontend/e2e/` or `e2e/`
- Use Playwright to drive the browser against the full Docker Compose stack
- Focus on user-visible workflows: login → navigate → edit → verify
- These complement (not replace) backend integration tests

For now, backend integration tests with `TestClient` provide the best coverage-to-cost ratio.

## Naming conventions

- Test classes: `Test{WorkflowName}Workflow`
- Test functions: `test_{complete_scenario_description}`
- File names: `test_{workflow_name}.py`
