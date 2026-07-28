# Documentation for filters system

This folder contains both the current filter implementation's concepts and the
longer-term workflow design that motivates it.

The current rewrite implements:

- recursive schemas and runtime data validation;
- a constrained set of composable function descriptions;
- dependency resolution and Python compilation;
- label-source, map, filter, and group runners;
- persisted workflows, instances, function definitions, and group assignments.

The subsystem is still under development. It does not yet have an HTTP router,
and its new database models do not yet have a committed Alembic migration.

The remaining documents are design notes. They intentionally describe planned
capabilities beyond the current code and should not be treated as an API
reference:

- [data-types.md](data-types.md): type-system motivation and target behavior
- [workflows.md](workflows.md): intended review and application workflow

Refer to [`backend/src/filters/`](../../backend/src/filters/) and its tests for
the implemented interface.
