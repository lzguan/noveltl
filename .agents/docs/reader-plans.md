# Reader plans

Discussed direction (2026-11-14), not implemented behavior or an approved
design.

## Shape

A separate server-rendered reader app in a top-level `reader/` directory of this
monorepo, built with React Router v7 framework mode (same React, Vite, Tailwind,
and Orval stack as `frontend/`). Its route loaders are the backend-for-frontend:
they call the FastAPI API server-side. The reader must never access PostgreSQL
directly, so caching, reader-specific tables, or a read replica can be added
later behind the API without changing it. A separate read database was
considered and deferred: it needs a sync pipeline and adds staleness for no
current load. The reader gets its own Orval client generated from the same
OpenAPI schema, not a shared one with `frontend/`.

Wanted feel: plain-link previous/contents/next navigation that works before
hydration, a single long chapter list, arrow-key navigation, reader settings
(font size, spacing, dark mode) stored in a cookie so SSR renders them, and
chapter-number URLs.

## Prerequisites

- Translation output never reaches chapters: actions only read `ChapterContent`
  and write stage-output files (see [chapter translation](chapter-translation.md)).
  An accept step that writes a translation into a translated novel is needed
  before machine translations can be read. Per-chapter publishing already
  exists (`chapter_is_public`, `POST /chapters/{id}/publish`), and
  `GET /chapters/{id}/content` allows anonymous reads, so the reader can be
  built against existing endpoints before the accept step lands.
- Anonymous reads already exist through `get_optional_user` with visibility
  filtering in [novels/router.py](../../backend/src/novels/router.py). Reader-shaped
  endpoints (chapter N with its current text, previous/next, contents) should be
  added to the API if the reader would otherwise compose several editor calls.
  Test anonymous access: leaking private novels is the main risk.

## Robustness

The user's main requirement is that the reader works and does not break
easily. Planned checks: regenerate both Orval clients from
`backend/openapi.yaml` on API changes and type-check both apps (the reader's
config differs: internal backend base URL, server-side fetch wrapper, likely no
Effect schemas, so clients stay separate rather than shared); backend tests for
anonymous visibility on reader endpoints; one or two Playwright smoke tests in
`e2e/` that load a chapter and follow next-chapter navigation.

## Division of work

Review closely: the accept step (likely a migration; follows the backend
permission pattern), reader endpoints and their visibility tests, and Compose
or devcontainer changes. Suitable for agent-driven building in a worktree: the
reader app itself, verified with Playwright screenshots at phone and desktop
widths, reviewing only its loaders closely.

This track is independent of the [evaluation plans](evaluation-plans.md) apart
from later ideas (reader reports as eval cases, eval-gated publishing).
