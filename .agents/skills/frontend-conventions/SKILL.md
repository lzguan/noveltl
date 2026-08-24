---
name: frontend-conventions
description: Review or change frontend state management, forms, asynchronous flows, or component and hook ownership using this project's conventions. Do not use for purely visual styling, backend work, or test-only tasks.
---

# Frontend Conventions

Keep implementations concrete, keep ownership clear, and avoid using lifecycle behavior as control flow.

## State and data flow

- Keep state with the component or hook that owns it.
- Store sources of truth; derive values that can be computed from current inputs.
- When a change in identity should discard all subordinate state, prefer remounting that subtree over synchronizing resets.
- Do not pass callbacks or values through intermediate layers when they are already available at the eventual call site.
- Keep an asynchronous operation together at the point that initiates it instead of splitting it across state and lifecycle reactions.

## Effects

- Use effects to synchronize with systems outside React or with lifecycle-dependent resources.
- Do not use effects to derive state, reset related state, or continue an operation initiated elsewhere.
- Requests driven by mounting or changing inputs may use an effect. Their loading transition may coincide with starting the request.
- Add cancellation when stale work could affect the current UI or when an external resource requires cleanup. Do not add it mechanically.

## Forms

- Form state hooks contain form state and explicit state transitions for sending, success, failure, and reset.
- Form state transitions update state only.
- Keep request orchestration, option selection, and other side effects outside form state hooks.
- Keep form implementations concrete unless demonstrated duplication justifies a shared abstraction.

## Types and abstractions

- Prefer inferred hook return types.
- Inline types that are local to a single component or function.
- Introduce shared types only for genuinely shared concepts.
- Do not create abstractions in anticipation of hypothetical reuse.

## Architecture boundaries

- Do not move responsibilities between architectural layers without user confirmation.
- When ownership is ambiguous, explain the viable placements and their consequences before editing.
- Treat changes to ownership, lifecycle, or data flow as architectural changes.

## UI composition

- Reuse existing project components before introducing new primitives or dependencies.
- Consult component-specific guidance only when the task actually involves that component system.
