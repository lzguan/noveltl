# Background job queue evaluation (Celery replacement)

**Last updated:** 2026-10-31

This document evaluates whether replacing Celery would simplify the
autolabels, filters, memory-agent, and translations workers.

## Scope and non-goals

- Scope: broker/worker runtime for dispatching background work.
- Non-goal: switching provider SDK clients to async I/O. That decision is
  independent from queue/runtime selection.

## Current lifecycle requirements (from code paths)

The required behavior is already mostly encoded as application state in
PostgreSQL models and lifecycle helpers, not in Celery-specific features.

### What Celery currently provides

- Asynchronous task delivery to worker processes.
- Delayed redelivery trigger (`countdown`) used by polling callbacks.
- Worker process model and deployment shape.

### What the application layer provides

- Durable job/task state, progress, and ownership/lease metadata in Postgres.
- Duplicate/lost-delivery safety via guarded `UPDATE ... WHERE` transitions.
- Retry/cancel/resume/start controls via explicit API operations.
- Sequential handoff rules (stage/task gating) and chapter ordering constraints.
- Recovery logic for expired claims and missing intermediate artifacts.

## Worker-by-worker audit

### Translations

- Strongest state machine and lease fencing:
  - claim/renew/finish/fail with lease expiry and `next_poll_at` gating
    (`backend/src/translations/tasks/claims.py`).
  - control operations (`start`, `resume`, `cancel`, `retry`) commit DB updates
    first, then dispatch (`backend/src/translations/service.py`).
  - stage handoff is application-controlled (`exitpoint`) and safe to retry
    after queue failure (`backend/src/translations/actions/celery_actions.py`).
- Delayed provider polling survives restarts because poll deadlines are stored
  in DB (`next_poll_at`) and re-dispatch can be reconstructed from state.
- Sequential stage dependencies per batch are explicit in DB statuses.

### Memory agent

- Job lease ownership with expiry and cooperative refresh.
- On claim takeover, abandoned `PROCESSING` tasks are reset to `PENDING`, which
  provides restart recovery (`backend/src/memory/agent/tasks/jobs.py`).
- API exposes start/retry/abort controls (`backend/src/memory/agent/service.py`).
- Sequential chapter processing comes from next-task claim ordering.

### Filters

- Queue/claim/clear lifecycle is persisted and guarded with row locks, and
  duplicate deliveries no-op when ownership/status no longer match
  (`backend/src/filters/lifecycle.py`, `backend/src/filters/runners/python/*`).
- Queue publish failures are converted to explicit failed state for recovery
  (`backend/src/filters/service.py`).
- Resume behavior is operation-specific (group can resume partially; output
  runners generally require empty outputs).

### Autolabels

- Progress and stale-job fencing are persisted (`auto_label_last_job_id` +
  status checks) (`backend/src/autolabels/worker/tasks.py`).
- Dispatch success/failure is explicitly written to row status/message
  (`backend/src/autolabels/service.py`).
- Simpler lifecycle than translations/memory (no lease renew/poll chain).

## Candidate comparison against required behavior

### 1) Keep Celery, strengthen app-owned semantics (baseline)

Pros:
- Lowest migration risk; existing semantics already live in DB code.
- Preserves current deployment model and test strategy.
- No forced rewrite of translation polling/lease logic.

Cons:
- Multiple Celery apps/configs to maintain.
- Need disciplined boundary docs/tests to avoid accidental Celery coupling.

Fit: **High**, because requirements are already app-owned.

### 2) Dramatiq (+ Redis)

Pros:
- Simpler API and middleware model.
- Comparable broker/deployment footprint.

Cons:
- Migration churn with little semantic gain: app still needs the same DB
  lifecycle logic for leases, polling gates, and recovery.
- Existing Celery integration tests and task wiring would be rewritten.

Fit: **Medium** (operationally plausible, limited payoff right now).

### 3) ARQ (async Redis queue)

Pros:
- Async-native worker handlers.

Cons:
- Pushes toward async refactors that are explicitly a separate decision.
- Similar semantic gap: DB state machine still required.
- Less aligned with current CPU-heavy autolabel process model.

Fit: **Low-Medium** for current constraints.

### 4) Temporal / workflow engine

Pros:
- Rich workflow primitives, timers, retries, cancellation.
- Strong built-in visibility.

Cons:
- Highest operational and migration complexity.
- Significant rewrite of app-owned workflow semantics into engine code.
- Overhead likely unjustified for current feature maturity and priority.

Fit: **Medium** long-term, **Low** near-term priority.

## Selected direction

**Do not migrate off Celery now.**

Rationale:
- The hard correctness requirements (durability, recovery, leases, safe
  handoffs, polling survival, sequencing) are already encoded in application
  state machines and SQL guards.
- Replacing Celery now mostly swaps transport plumbing while preserving the same
  core lifecycle complexity.
- The issue is lower priority than current feature work and dependency upkeep.

## Incremental rollout plan (now)

1. **Codify transport boundary**
   - Keep dispatcher interfaces per domain (`enqueue`, delay dispatch).
   - Document that lifecycle invariants must remain DB-enforced.
2. **Expand regression coverage where risk is highest**
   - Queue publish failure after DB commit.
   - Duplicate delivery + stale ownership attempts.
   - Lease expiry takeover and safe continuation.
   - Lost poll message recovery from persisted `next_poll_at`.
   - Worker restart mid-stage and resume/retry correctness.
3. **Operational hardening**
   - Keep worker-specific isolation and prefetch settings.
   - Add runbook entries for stuck claims and replay controls by domain.

## Migration trigger criteria (future)

Re-open migration only when at least one is true:
- Celery-specific operational incidents dominate worker outages.
- Required features cannot be met without substantial Celery-specific
  workarounds.
- A replacement can be introduced behind dispatcher interfaces with measurable
  operational improvement and no regression in DB recovery guarantees.

## If migration is later approved: reviewable implementation slices

1. **Dual-dispatch adapter layer**
   - Keep current DB lifecycle code unchanged.
   - Add alternate transport implementation for one low-risk path first.
2. **Canary worker domain**
   - Start with autolabels or filters (simpler than translations polling chain).
3. **Parity regression suite (required gate)**
   - Real queue + real database integration tests for duplicate/lost delivery,
     retries/cancel, lease expiry takeover, delayed polling recovery, and
     sequential stage/chapter correctness.
4. **Domain-by-domain rollout**
   - Migrate one worker class at a time with rollback path to Celery dispatch.
5. **Translations last**
   - Migrate only after proving delayed poll + lease handoff parity under worker
     restarts and queue failures.
