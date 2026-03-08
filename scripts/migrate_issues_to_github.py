#!/usr/bin/env python3
"""
One-time migration script to create GitHub issues from docs/issues.md.

Usage:
    # Using a GitHub personal access token:
    GH_TOKEN=ghp_xxx python scripts/migrate_issues_to_github.py

    # Or pass the token directly:
    python scripts/migrate_issues_to_github.py --token ghp_xxx

    # Dry run (prints issues without creating them):
    python scripts/migrate_issues_to_github.py --dry-run

Requires: pip install requests

After running successfully, delete this script — it is not needed again.
"""

import argparse
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

REPO = "lzguan/NovelTL_Dev"
API_BASE = f"https://api.github.com/repos/{REPO}"

ISSUES = [
    {
        "title": "Missing `from_attributes=True` on some schemas",
        "labels": ["bug"],
        "body": (
            "**Status**: Verified ✓\n\n"
            "`Novel`, `RawChapter`, `RawChapterRevision` in `backend/src/novels/schemas.py` are "
            "missing `model_config = ConfigDict(from_attributes=True)`, which prevents Pydantic from "
            "converting SQLAlchemy ORM model instances to schema instances.\n\n"
            "**Current State**: Only `RawChapterRevisionMeta` has this configuration (line 130).\n\n"
            "**Impact**: Router endpoints that return these schemas directly from service layer ORM "
            "objects will fail.\n\n"
            "**Fix**: Add to each schema:\n"
            "```python\n"
            "model_config = ConfigDict(from_attributes=True)\n"
            "```"
        ),
    },
    {
        "title": "Broad exception handling swallows debug info",
        "labels": ["bug"],
        "body": (
            "**Status**: Verified ✓\n\n"
            "`backend/src/novels/service.py` has 9 instances of `except Exception as e:` that catch "
            "all exceptions and raise `UnknownError`, losing the original exception context and stack trace.\n\n"
            "**Examples**:\n"
            "- Line 381: `insert_novel()` — catches everything after specific IntegrityError/DataError handling\n"
            "- Line 428: `modify_novel()` — catches everything\n"
            "- Line 482, 540, 589: Similar pattern in other functions\n\n"
            "**Impact**: Makes debugging production issues difficult. Original exception types and messages are lost.\n\n"
            "**Better Approach**: Log original exception before re-raising, or let unexpected exceptions "
            "propagate to global handler:\n"
            "```python\n"
            'except Exception as e:\n'
            '    logger.exception(f"Unexpected error in insert_novel: {e}")\n'
            '    raise UnknownError from e\n'
            "```"
        ),
    },
    {
        "title": "Security: No rate limiting on `/token` endpoint",
        "labels": ["security"],
        "body": (
            "**Status**: Verified ✓\n\n"
            "`backend/src/auth/router.py` `POST /token` endpoint (line 26) has no rate limiting, "
            "making it vulnerable to brute force password attacks.\n\n"
            "**Current Protection**: None visible in router or dependencies.\n\n"
            "**Recommended Solutions**:\n"
            "1. Use `slowapi` library with Redis backend for distributed rate limiting\n"
            "2. Implement account lockout after N failed attempts\n"
            "3. Add CAPTCHA after repeated failures\n"
            "4. Monitor for suspicious login patterns"
        ),
    },
    {
        "title": "Security: Consider refresh tokens",
        "labels": ["security", "enhancement"],
        "body": (
            "`ACCESS_TOKEN_EXPIRE_MINUTES = 30` is short. "
            "Refresh tokens would improve UX without compromising security."
        ),
    },
    {
        "title": "Performance: Multiple sessions per worker task",
        "labels": ["performance"],
        "body": (
            "**Status**: Verified ✓\n\n"
            "`backend/src/autolabels/worker/tasks.py` creates 6 separate `SessionLocal()` contexts "
            "within `autolabel_infer()` task (lines 38, 47, 56, 65, 104, 112).\n\n"
            "**Impact**: Each context acquires a new database connection from the pool. For high-throughput "
            "worker tasks, this creates unnecessary connection churn.\n\n"
            "**Why It Happens**: Error handling — different exception paths each need to update the database, "
            "so separate sessions prevent rollback conflicts.\n\n"
            "**Better Approach**: Use a single session with savepoints for partial rollback, or refactor to "
            "consolidate error handling."
        ),
    },
    {
        "title": "Performance: Missing indexes",
        "labels": ["performance"],
        "body": (
            "**Status**: Verified ✓\n\n"
            "Migration `backend/alembic/versions/06741dac5042_initial.py` is missing indexes on "
            "frequently queried columns:\n\n"
            "**Missing Indexes**:\n"
            "1. `RawChapter.raw_chapter_num` — Used for sorting chapters (ORDER BY), not covered by "
            "composite unique constraint `(raw_chapter_num, novel_id)`\n"
            "2. `Contributor.user_id` — Used in JOIN queries to find user's novels/label groups "
            "(foreign key not auto-indexed in PostgreSQL)\n"
            "3. `LabelContributor.user_id` — Same issue as above\n\n"
            "**Impact**: Sequential scans on tables with many rows. Particularly problematic for users with "
            "many novels or queries like \"get all chapters for novel X ordered by chapter number\".\n\n"
            "**Fix**: Add indexes in new migration:\n"
            "```sql\n"
            "CREATE INDEX ix_raw_chapter_num ON raw_chapters(raw_chapter_num);\n"
            "CREATE INDEX ix_novel_contributors_user_id ON novel_contributors(user_id);\n"
            "CREATE INDEX ix_label_group_contributors_user_id ON label_group_contributors(user_id);\n"
            "```"
        ),
    },
    {
        "title": "Technical Debt: \"Raw\" prefix on Chapter models is misleading",
        "labels": ["refactor"],
        "body": (
            "**Status**: Planned refactoring\n\n"
            "The models `RawChapter` and `RawChapterRevision` use the \"Raw\" prefix from early project "
            "design when there was a planned `TranslatedChapter` class. Since that feature was removed, "
            "the \"Raw\" prefix is now confusing and should be renamed.\n\n"
            "**Proposed Changes**:\n"
            "- `RawChapter` → `Chapter`\n"
            "- `RawChapterRevision` → `ChapterRevision`\n"
            "- Update all references in:\n"
            "  - Database models (`backend/src/novels/models.py`)\n"
            "  - API endpoints (currently `/chapters`, `/revisions` — done, corresponding changes in frontend done)\n"
            "  - Schemas (`backend/src/novels/schemas.py`)\n"
            "  - Service functions\n"
            "  - Documentation\n\n"
            "**Affected Files**:\n"
            "- `backend/src/novels/models.py` — Model class names\n"
            "- `backend/src/novels/schemas.py` — Schema class names\n"
            "- `backend/src/novels/router.py` — Type hints\n"
            "- `backend/src/novels/service.py` — Type hints and queries\n"
            "- `backend/src/labels/models.py` — Foreign key relationships\n"
            "- `backend/src/autolabels/models.py` — Foreign key relationships\n"
            "- All documentation files\n"
            "- Database migration (table rename: `raw_chapters` → `chapters`, `raw_chapter_revisions` → `chapter_revisions`)\n\n"
            "**Impact**: This is a breaking database migration. Requires careful coordination:\n"
            "1. Create migration to rename tables and columns\n"
            "2. Update all code references\n"
            "3. Update API response field names (breaking API change)\n\n"
            "**Recommendation**: Schedule as part of larger refactoring before v1.0 release."
        ),
    },
    {
        "title": "Refactor: Replace `novel_parent_id` with Novel Relations association table",
        "labels": ["refactor", "enhancement"],
        "body": (
            "**Status**: Planned\n\n"
            "`backend/src/novels/models.py` uses a `novel_parent_id` FK to model a single-parent tree "
            "of novels. This is too rigid (one parent, one relation type) and allows circular references "
            "(self-reference, A→B→A, deeper cycles) with no validation.\n\n"
            "**Proposed replacement:** Drop `novel_parent_id` and add an association table:\n\n"
            "```sql\n"
            "CREATE TABLE novel_relations (\n"
            "    novel_relation_id SERIAL PRIMARY KEY,\n"
            "    novel_id_1 INT NOT NULL REFERENCES novels(novel_id),\n"
            "    novel_id_2 INT NOT NULL REFERENCES novels(novel_id),\n"
            "    relation VARCHAR NOT NULL,  -- enum/protocol TBD\n"
            "    CHECK (novel_id_1 != novel_id_2)\n"
            ");\n"
            "```\n\n"
            "**Design decisions needed:**\n\n"
            "1. **Relation type protocol** — define the allowed values for `relation` and their semantics. "
            "Starting candidates:\n"
            "   - `translation` — novel_id_1 is the source, novel_id_2 is its translation (directed)\n"
            "   - `recommended` — symmetric suggestion between two novels\n"
            "   - Others TBD (`sequel`/`prequel`?, `alternate_version`?)\n\n"
            "2. **Directionality** — some relations are asymmetric (translation: source → target), others "
            "symmetric (recommended). Either encode this per-type in backend logic, or add a `directed: bool` column.\n\n"
            "3. **Uniqueness** — should `(A, B, translation)` be unique? If symmetric relations enforce "
            "canonical ordering (e.g., `novel_id_1 < novel_id_2`), a unique constraint on "
            "`(novel_id_1, novel_id_2, relation)` suffices. Directed relations allow both `(A, B)` and `(B, A)`.\n\n"
            "4. **Permission implications** — does a relation grant cross-novel access? E.g., can contributors "
            "of a source novel see a linked restricted translation? This interacts with the planned alias system "
            "(see Planned Features: Permissions issue).\n\n"
            "**Affected files:** `novels/models.py` (drop `novel_parent_id`, add `NovelRelation` model), "
            "`novels/schemas.py`, `novels/service.py` (new CRUD for relations), `novels/router.py` "
            "(new endpoints), new migration."
        ),
    },
    {
        "title": "API: Pagination on list endpoints",
        "labels": ["enhancement"],
        "body": (
            "**Status**: Verified ✓\n\n"
            "List endpoints in `backend/src/novels/router.py` return all matching records without pagination:\n"
            "- `GET /novels` (line 46) — No `limit`/`offset` parameters\n"
            "- `GET /novels/mine` (line 66) — No pagination\n"
            "- Similar issues on other list endpoints\n\n"
            "**Current Behavior**:\n"
            "```python\n"
            "@router.get('/novels', response_model=list[schemas.Novel])\n"
            "async def read_novels(...):\n"
            "    novels = query_novels_by_title(db, current_user, title_contains)\n"
            "    return novels  # Returns ALL matching novels\n"
            "```\n\n"
            "**Impact**:\n"
            "- Large response payloads for users with many novels (hundreds of KB)\n"
            "- Slow queries as dataset grows\n"
            "- Poor UX — frontend has to load everything upfront\n\n"
            "**Fix**: Add pagination parameters:\n"
            "```python\n"
            "@router.get('/novels')\n"
            "async def read_novels(\n"
            "    limit: int = Query(default=50, le=100),\n"
            "    offset: int = Query(default=0, ge=0),\n"
            "    ...\n"
            "):\n"
            "    novels = query_novels_by_title(db, current_user, title_contains, limit, offset)\n"
            "    return novels\n"
            "```"
        ),
    },
    {
        "title": "Testing: Insufficient code coverage",
        "labels": ["testing"],
        "body": (
            "**Status**: To Do\n\n"
            "Test coverage is currently incomplete across multiple modules.\n\n"
            "**Current State**:\n"
            "- Test suite exists in `backend/tests/` with fixtures and module-specific test files\n"
            "- Coverage reporting configured in `pyproject.toml` with pytest-cov\n"
            "- Many modules have tests but coverage percentage not documented\n"
            "- Critical paths (authentication, permissions, database operations) need verification\n\n"
            "**Gaps**:\n"
            "- No coverage threshold enforcement in CI/CD\n"
            "- Edge cases and error paths may be undertested\n"
            "- Integration tests exist but unit test coverage unknown\n"
            "- Worker tasks (NER processing) coverage unclear\n\n"
            "**Impact**:\n"
            "- Bugs may slip through in untested code paths\n"
            "- Refactoring is riskier without comprehensive test coverage\n"
            "- Difficult to assess which code is safe to modify\n"
            "- Technical debt accumulates in untested areas\n\n"
            "**Recommended Approach**:\n"
            "1. Measure baseline coverage: `pytest --cov=src --cov-report=term-missing`\n"
            "2. Set minimum thresholds in `pyproject.toml` (e.g., 80% overall, 90% for critical modules)\n"
            "3. Add coverage reporting to CI pipeline with failure on threshold miss\n"
            "4. Prioritize coverage improvements:\n"
            "   - Authentication flows (login, token refresh, permissions)\n"
            "   - Data validation (schema validation, circular reference checks)\n"
            "   - API endpoints (error handling, edge cases)\n"
            "   - Worker tasks (job processing, failure scenarios)\n"
            "5. Track coverage trends over time with tools like codecov or coveralls\n\n"
            "**Quick Start**:\n"
            "```bash\n"
            "# Generate coverage report\n"
            "pytest --cov=src --cov-report=html --cov-report=term-missing\n\n"
            "# View detailed HTML report\n"
            "open htmlcov/index.html\n\n"
            "# Fail if coverage below 80%\n"
            "pytest --cov=src --cov-fail-under=80\n"
            "```"
        ),
    },
    {
        "title": "Planned Feature: AutoLabel Job Timeout",
        "labels": ["enhancement"],
        "body": (
            "Worker tasks that hang (OOM, model deadlock, network partition) leave AutoLabel rows stuck in "
            "`PROCESSING` forever with no recovery path.\n\n"
            "**Proposed approach:**\n\n"
            "1. **Add `job_timeout` to `NERModelParamsBase`** — each model's param schema inherits a "
            "`job_timeout: int` field (seconds). Defaults can differ per model based on expected inference time. "
            "The worker wraps the inference call with `asyncio.wait_for` (or `asyncio.timeout` on Python 3.11+):\n"
            "   ```python\n"
            "   result = await asyncio.wait_for(\n"
            "       run_inference(text, params),\n"
            "       timeout=params.job_timeout\n"
            "   )\n"
            "   ```\n"
            "   On `TimeoutError`, write `status=FAILED`, `message=\"Job timed out.\"`.\n\n"
            "2. **Add `auto_label_timeout_time` column** — store the computed deadline "
            "(`enqueued_at + job_timeout`) on the AutoLabel row so it's visible to external observers without "
            "needing to re-derive it.\n\n"
            "3. **Cron job cleanup (lower priority)** — in case of worker crash/disconnect the "
            "`asyncio.timeout` path never runs. A cron job can sweep for rows where "
            "`auto_label_status = 'processing'` and `auto_label_timeout_time < now()`, resetting them "
            "to `PENDING` with a new `job_id` to invalidate any zombie worker that reconnects.\n\n"
            "**Affected files:** `autolabels/constants.py` (`NERModelParamsBase`), "
            "`autolabels/worker/tasks.py`, new migration for `auto_label_timeout_time` column."
        ),
    },
    {
        "title": "Planned Feature: Batch Inference Optimization",
        "labels": ["enhancement"],
        "body": (
            "**Current:** One chapter per worker job (one ARQ task per AutoLabel row).\n"
            "**Proposed:** Batch multiple chapters into a single worker task for a forward pass.\n\n"
            "**Benefits:**\n"
            "- Amortize model loading overhead (~500ms per job → ~500ms per batch)\n"
            "- Better GPU utilization\n"
            "- 5-10x throughput improvement at scale\n\n"
            "**Challenges:**\n"
            "- ARQ job granularity — current design is one job per `auto_label_id`; batching requires "
            "either a new job type or grouping logic at enqueue time\n"
            "- Error isolation — one chapter's failure shouldn't FAIL the entire batch; need per-row "
            "error tracking within a batch job\n"
            "- Variable chapter lengths affect optimal batch size"
        ),
    },
    {
        "title": "Planned Features: Permissions (Alias System & Publicly Editable Label Groups)",
        "labels": ["enhancement"],
        "body": (
            "### Alias System for Restricted Novels\n\n"
            "Novels can have multiple aliases (e.g., Chinese title, English title). When a user creates "
            "a novel, check for matching aliases against existing restricted novels and send collaboration "
            "requests to owners of matching novels. Reduces duplicate translation efforts. See "
            "`docs/permissions.md` (Visibility Levels section) for context on Restricted visibility.\n\n"
            "### Publicly Editable Label Groups\n\n"
            "Label groups will support a `publicly_editable` flag. When enabled, any user can contribute "
            "labels to the group (useful for community labeling projects). Requires the parent novel to also "
            "be public. Individual label `label_dirty` flag tracks manual edits."
        ),
    },
    {
        "title": "Schema: Label Group Lineage Tracking",
        "labels": ["enhancement"],
        "body": (
            "**Status:** Discussion\n\n"
            "The `create_copy` option in `apply_filter` creates a new label group but doesn't record where "
            "it came from. We need a way to track which label group was derived from which, for provenance "
            "and potential undo.\n\n"
            "### Option A: Simple FK on `label_groups`\n\n"
            "Add a nullable self-referencing FK:\n\n"
            "```\n"
            "label_groups\n"
            "  ...\n"
            "  source_label_group_id  INTEGER  FK → label_groups  NULLABLE\n"
            "```\n\n"
            "- Copy → original backlink: `WHERE source_label_group_id = :original_id`\n"
            "- Provenance chain: follow `source_label_group_id` upward to root\n"
            "- Zero overhead for non-copy groups (just `NULL`)\n"
            "- Simple, sufficient if copies always have exactly one source\n\n"
            "### Option B: Association table with metadata\n\n"
            "```\n"
            "label_group_lineage\n"
            "  source_label_group_id   FK → label_groups  PK\n"
            "  derived_label_group_id  FK → label_groups  PK\n"
            "  operation               VARCHAR             -- e.g. \"score_filter_apply\"\n"
            "  created_at              TIMESTAMP\n"
            "```\n\n"
            "- Supports multiple sources per derived group (e.g., merging data from two groups)\n"
            "- Stores what operation created the copy and when\n"
            "- More flexible but heavier\n\n"
            "### Open questions\n\n"
            "- Is there a real use case for multiple-source derivation, or is single-parent always enough?\n"
            "- Should the UI expose lineage to users (transparent) or hide it (undo/redo chain)? "
            "Leaning toward transparent — just show all groups and let the user see \"copied from X.\""
        ),
    },
]


def ensure_labels(session: requests.Session) -> None:
    """Create any labels that don't already exist."""
    needed = {label for issue in ISSUES for label in issue["labels"]}
    label_colors = {
        "bug": "d73a4a",
        "enhancement": "a2eeef",
        "security": "e4e669",
        "performance": "f9d0c4",
        "refactor": "c5def5",
        "testing": "bfd4f2",
    }

    resp = session.get(f"{API_BASE}/labels", params={"per_page": 100})
    resp.raise_for_status()
    existing = {label["name"] for label in resp.json()}

    for name in sorted(needed - existing):
        color = label_colors.get(name, "ededed")
        resp = session.post(
            f"{API_BASE}/labels",
            json={"name": name, "color": color},
        )
        if resp.status_code == 201:
            print(f"  Created label: {name}")
        else:
            print(f"  Label '{name}' — {resp.status_code}: {resp.text}")


def create_issues(session: requests.Session, *, dry_run: bool = False) -> None:
    """Create GitHub issues from the ISSUES list."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Creating {len(ISSUES)} issues...\n")

    for i, issue in enumerate(ISSUES, 1):
        title = issue["title"]
        if dry_run:
            print(f"  [{i}/{len(ISSUES)}] {title}")
            print(f"    Labels: {', '.join(issue['labels'])}")
            print(f"    Body length: {len(issue['body'])} chars\n")
            continue

        resp = session.post(
            f"{API_BASE}/issues",
            json={
                "title": title,
                "body": issue["body"],
                "labels": issue["labels"],
            },
        )

        if resp.status_code == 201:
            number = resp.json()["number"]
            print(f"  [{i}/{len(ISSUES)}] #{number} — {title}")
        else:
            print(f"  [{i}/{len(ISSUES)}] FAILED ({resp.status_code}) — {title}")
            print(f"    {resp.text}")

        # Respect GitHub API rate limits
        time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate docs/issues.md to GitHub Issues"
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", "")),
        help="GitHub personal access token (or set GH_TOKEN env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print issues without creating them",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.token:
        sys.exit(
            "Error: provide a GitHub token via --token or GH_TOKEN environment variable"
        )

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {args.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )

    if not args.dry_run:
        print("Ensuring labels exist...")
        ensure_labels(session)

    create_issues(session, dry_run=args.dry_run)
    print("\nDone!")


if __name__ == "__main__":
    main()
