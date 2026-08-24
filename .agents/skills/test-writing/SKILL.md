---
name: test-writing
description: Identify a producer's service and its consumer contract, decide whether it needs permanent regression coverage, then select, write, review, or debug the narrowest faithful test. Do not use merely to execute an already specified check.
---

# Test Writing

The objective of a test is to provide durable evidence that a contract relied upon by a named consumer continues to hold.

## Identify the service and contract

Before writing a permanent test, state:

> `[Producer]` provides `[service]` to `[consumer]`, which relies on `[guarantee]` to accomplish `[goal]` when `[conditions]`.

Determine:

- What service or capability the producer provides.
- Who actually consumes it and why.
- What must remain true for the service to remain useful.
- Where that reliance is evidenced: a call site, public interface, requirement, established invariant, or regression.
- What observable boundary exposes the guarantee.

A service may be an API, algorithm, state manager, parser, component, database constraint, worker capability, or other producer behavior. A consumer may be an end user, component, module, service, worker, or operator. Do not invent a consumer or treat every internal function as a stable service merely to justify testing it.

## Qualify permanent coverage

Permanent coverage requires all of the following:

- An evidenced consumer contract.
- A plausible defect and its consumer-visible consequence.
- No existing test or static check that clearly fails when this exact guarantee is violated.
- At least one material reason for regression protection: a meaningful transformation or invariant; risk of data loss, corruption, security, permission failure, or stale state; boundary compatibility; a known regression or race; or a critical cross-boundary workflow.

The mere presence of an API, database, or other boundary does not qualify every operation on that boundary. If permanent coverage is unjustified but additional evidence is still needed, use an existing static check or one-time verification.

## Select the test boundary

Start at the narrowest interface used by the consumer that can faithfully observe the contract. Test categories may compose: keep lower layers real when their transactions, constraints, serialization, authorization, or other semantics are part of the guarantee.

| Contract | Test type |
| --- | --- |
| Isolated deterministic logic, state transitions, or meaningful edge cases | Unit test |
| Substantial user interaction owned by a component | Component test |
| Request validation, authorization, status codes, or serialization | API test |
| Queries, constraints, transactions, persistence, or migrations | Integration test using the real test database |
| Queue, cache, worker, or other infrastructure semantics | Integration test using the real service |
| Interactions among several application services | Service-level integration test |
| Browser behavior or a workflow spanning frontend and backend | End-to-end test |
| Cross-boundary schemas or generated interfaces | Contract, schema, generation, or type check |
| Stochastic or live external-model behavior | Separate opt-in evaluation or live test |
| Formatting, imports, static typing, trivial wiring, or purely static markup with no conditional semantic or accessibility contract | Static check or one-time verification; no permanent behavioral test |

Do not treat hooks as a separate test category. `renderHook` is only a unit-test harness when a reusable hook itself provides an evidenced state or lifecycle contract and no host-component behavior is relevant.

For concurrency regressions, use the lowest boundary that faithfully reproduces the race. Use an end-to-end test only when browser lifecycle or transport timing is essential.

## Prefer real collaborators

Use real collaborators by default. Classify a boundary by ownership and semantics, not its import path: a generated client or local adapter may represent an external system, while another local module may remain an internal implementation detail.

Introduce a test double only when there is a specific reason the real collaborator cannot faithfully or practically be used, such as:

- It is paid, nondeterministic, destructive, or externally unavailable.
- The test must deterministically produce a rare failure, timeout, or race.
- Real execution would make a focused test prohibitively slow.
- It is unrelated to the contract and requires substantial infrastructure.
- The external dependency does not exist yet.

Convenient setup, an easily replaced internal function, or a desire to assert call wiring are not sufficient reasons. Do not replace an integration whose semantics are part of the contract.

When a test double is justified:

- State why the real collaborator is impractical and which semantics the double omits.
- Replace a true external boundary or an owned public or injected seam; do not replace a private helper merely to make call assertions possible.
- Assert consumer-visible results. Payloads, effects, or invocation counts may be asserted when that boundary interaction is itself the contract; do not assert incidental calls.
- Keep fake inputs and responses representative of the real contract.
- If omitted semantics matter, cover them separately using the real dependency or explicitly report the gap.
- Treat a large test-double graph as evidence that the test is at the wrong boundary.

## Write contract cases

- Assert observable results rather than internal calls or implementation structure.
- Cover only the meaningful success, boundary, and failure conditions of the stated contract.
- For a regression, state the contract that was violated and add coverage at the narrowest faithful boundary.

## One-time verification

Use a temporary script or focused manual exercise when evidence is needed but the contract does not qualify for permanent regression protection. It may validate an assumption, reproduce a condition, exercise an operation, or inspect an output.

Keep temporary scripts outside the repository by default, make each answer one narrow question, report the observed result, and remove it afterward unless the user asks to keep it.

## Scope and verification

- Keep new tests scoped to the requested change. Existing untested behavior does not authorize a broader testing project.
- If faithful coverage would be disproportionately expensive or brittle, explain the tradeoff and ask the user before proceeding.
- If an existing test conflicts with the intended behavior, raise the conflict instead of preserving the test blindly.
- Run the most focused relevant tests first, then broaden verification in proportion to the change's risk.
