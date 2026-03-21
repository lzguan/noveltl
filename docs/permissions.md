# Permissions System

**Last Updated**: March 20, 2026     
**Status**: Complete

This document describes the access control and permission system for NovelTL, including visibility levels, contributor roles, permission helper design, and authorization patterns.

---

## Table of Contents

1. [Glossary](#glossary)
2. [Overview](#overview)
3. [User Types](#user-types)
4. [Permission Helper Functions](#permission-helper-functions)
   - [What They Are](#what-they-are)
   - [Naming Convention](#naming-convention)
   - [Generic Type Signatures](#generic-type-signatures)
   - [How They Work](#how-they-work)
   - [Insert Helpers and Insert-From-Select](#insert-helpers-and-insert-from-select)
5. [Novel Permissions](#novel-permissions)
   - [Visibility Levels](#visibility-levels)
   - [Contributor Roles](#contributor-roles)
   - [Chapter Revision Visibility](#chapter-revision-visibility)
   - [Novel Helper Functions](#novel-helper-functions)
6. [Label Group Permissions](#label-group-permissions)
   - [Label Contributor Roles](#label-contributor-roles)
   - [Cascading Permission Model](#cascading-permission-model)
   - [Label Helper Functions](#label-helper-functions)
7. [AutoLabel Permissions](#autolabel-permissions)
8. [Filter Permissions](#filter-permissions)
9. [Authorization Patterns](#authorization-patterns)
   - [SELECT (Read)](#select-read)
   - [UPDATE (Edit)](#update-edit)
   - [INSERT (Create — No Parent)](#insert-create--no-parent)
   - [INSERT (Create — With Parent)](#insert-create--with-parent)
   - [DELETE](#delete)
10. [Security Considerations](#security-considerations)
    - [Zero-Knowledge Resource Privacy](#zero-knowledge-resource-privacy)
    - [Guest Access](#guest-access)
    - [Admin Bypass](#admin-bypass)
11. [Relevant Files](#relevant-files)
12. [See Also](#see-also)

---

## Glossary

| Term | Definition |
|------|------------|
| **Permission helper** | A function that takes a SQLAlchemy statement and returns a modified statement with permission WHERE clauses appended. |
| **Visibility level** | An integer enum (`Private`, `Restricted`, `Unlisted`, `Public`) controlling novel read access. |
| **Contributor** | A user associated with a resource (novel or label group) via a contributor table, with a specific role. |
| **Insert-from-select** | A SQL pattern (`INSERT INTO ... SELECT ...`) used to atomically create a row while verifying parent permissions in the SELECT clause. |
| **Cascading permissions** | Child resources (label groups, label data, labels) inherit access restrictions from their parent resources (novels, chapter revisions). |
| **Zero-knowledge privacy** | A user cannot distinguish between a resource that does not exist and one they lack access to. |

---

## Overview

NovelTL uses a fine-grained permission system based on:
1. **User Types** — Admin vs. regular user
2. **Visibility Levels** — Novel exposure control (private, restricted, unlisted, public)
3. **Contributors** — Role-based access to specific resources (owner, editor, viewer)
4. **Request Types** — Combinations of the above give different access to different request types (e.g. create, read, update)

Permissions are enforced at the database query level via **permission helper functions** that modify SQLAlchemy statements before execution. This codebase intentionally limits ORM usage; most writes use SQLAlchemy Core statements (`insert`, `update`, `delete`) rather than `session.add()`.

---

## User Types

### Admin

**Admins bypass ALL permission checks.** Every permission helper checks `current_user.user_type == UserType.ADMIN` and returns the unmodified statement if true:

- Full access to all resources regardless of visibility
- No contributor relationship required
- Bypasses all role-based restrictions

**Trade-off:** Requires complete trust in admin users. There is no audit trail or fine-grained admin permissions.

### User

- Subject to visibility level restrictions
- Must be a contributor with appropriate role to access private/restricted resources
- Must have editor/owner role to modify resources

**Note:** User type is set at account creation and stored in `users.user_type`. The `UserType` enum is defined in `backend/src/auth/constants.py`.

---

## Permission Helper Functions

### What They Are

Permission helpers are functions that take a SQLAlchemy statement (Select, Update, Delete, or a Select used for insert-from-select) and return a modified version with permission WHERE clauses applied.

**Why this approach:**
- **Single source of truth** — all permission logic for a resource lives in one function
- **Consistency** — the same rules apply everywhere, eliminating edge cases from copy-paste
- **Maintainability** — changing visibility rules updates all queries automatically
- **Auditability** — one file per module to review all access control logic

### Naming Convention

```
{resource}_mod_access_{operation}
```

| Operation | Statement Type | Purpose |
|-----------|---------------|---------|
| `*_select` | `Select` | Read access |
| `*_insert` | `Select` (used in insert-from-select) | Parent access verification for resource creation |
| `*_update` | `Update` | Edit access |
| `*_delete` | `Delete` | Removal access (typically most restrictive) |

### Generic Type Signatures

Permission helpers use **PEP 695 generic type parameters** to preserve SQLAlchemy's type information through the permission layer. This ensures that the return type matches the input type exactly, so downstream code retains full type hinting:

```python
def novel_mod_access_select[T : Select[tuple[Any, ...]]](q : T, current_user : User | None) -> T:
    ...

def novel_mod_access_update[T : Update](stmt : T, current_user : User) -> T:
    ...

def chapter_mod_access_insert[T : Select[tuple[Any, ...]]](stmt : T, current_user : User, novel_id : int) -> T:
    ...

def revision_mod_access_delete[T : Delete](stmt : T, current_user : User) -> T:
    ...
```

Key details:
- `*_select` helpers are generic over `Select[tuple[Any, ...]]` — any Select statement with any column tuple
- `*_insert` helpers are also generic over `Select` because they modify the SELECT portion of an insert-from-select (see below)
- `*_update` helpers are generic over `Update`
- `*_delete` helpers are generic over `Delete`
- The generic `T` bound ensures the exact statement subtype is preserved, so callers do not lose query type information when passing through permission checks

### How They Work

Every helper follows the same decision tree:

1. **Admin?** → Return unmodified statement (full bypass)
2. **Guest (`None`)?** → Filter to public/unlisted resources only
3. **Regular user** → Add OR conditions: resource is public/unlisted, OR user is a contributor with the required role

```python
def novel_mod_access_select[T : Select[tuple[Any, ...]]](q : T, current_user : User | None) -> T:
    if current_user is None:
        return q.where(Novel.novel_visibility >= Visibility.UNLISTED)
    elif current_user.user_type != UserType.ADMIN:
        return q.where(or_(
            Novel.novel_visibility >= Visibility.UNLISTED,
            exists(
                select(1).select_from(Contributor)
                .where(Contributor.novel_id == Novel.novel_id)
                .where(Contributor.user_id == current_user.user_id)
            )
        ))
    return q
```

### Insert Helpers and Insert-From-Select

This is a critical pattern in the codebase. When creating a child resource (e.g., a raw chapter under a novel), the code must verify that the user has access to the parent resource. Rather than doing a separate verification query followed by an ORM insert, this codebase uses **insert-from-select**: a `SELECT` of literal values with permission WHERE clauses, fed into `INSERT(...).from_select(...)`.

**Why `*_mod_access_insert` helpers accept `Select` statements:**

The insert helpers do not modify INSERT statements directly. Instead, they modify the SELECT statement that will be used as the data source for the INSERT. The permission check and the insert happen atomically in one SQL statement — if the permission check fails, the SELECT returns zero rows, so nothing is inserted.

```python
# Actual pattern from the codebase:
def insert_chapter(db, current_user, novel_id, request):
    data = list(request.model_dump().items())
    data.append(('novel_id', novel_id))
    cols = [k for k, _ in data]

    # Build a SELECT of literal values (the row to be inserted)
    vals = select(*[literal(v) for _, v in data])

    # Attach permission WHERE clauses to the SELECT
    vals = chapter_mod_access_insert(vals, current_user, novel_id)

    # Atomically: SELECT checks permissions, INSERT creates the row
    stmt = insert(Chapter).from_select(cols, vals).returning(Chapter)
    result = db.execute(stmt)
```

**What the helper does internally:**

```python
def chapter_mod_access_insert[T : Select[tuple[Any, ...]]](
    stmt : T, current_user : User, novel_id : int
) -> T:
    if current_user.user_type != UserType.ADMIN:
        return stmt.where(
            exists(
                select(1).select_from(Contributor)
                .where(Contributor.novel_id == novel_id)
                .where(Contributor.user_id == current_user.user_id)
                .where(Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR]))
            )
        )
    return stmt
```

The SELECT of literals is unconditional (`SELECT 'value1', 'value2', ...`), so it would always return one row. The permission helper adds a WHERE clause like `WHERE EXISTS(... contributor check ...)`. If the user lacks access, the WHERE fails, the SELECT returns zero rows, and the INSERT inserts nothing. The caller detects this via `NoResultFound` or `scalar_one_or_none()`.

**Contrast with no-parent resources:** Resources that have no parent requiring permission checks (e.g., novels themselves) simply use `db.add()` since the only requirement is that the user is logged in.

---

## Novel Permissions

### Visibility Levels

Novels have four visibility levels controlling _read_ access (stored as integers in `novels.novel_visibility`, defined as a Python `IntEnum`):

| Level | Name | Search | ID Query | Create Check | Description |
|-------|------|--------|----------|--------------|-------------|
| 0 | **Private** | ❌ | Contributors only | ❌ | Only contributors can access |
| 1 | **Restricted** | ❌ | Contributors only | Alias match → request | Like private, but alias matching enabled |
| 2 | **Unlisted** | ❌ | ✅ Anyone | ✅ Anyone | Accessible by direct link, hidden from search |
| 3 | **Public** | ✅ Anyone | ✅ Anyone | ✅ Anyone | Fully public |

**Request type definitions:**

1. **Search/Filter Queries** — `GET /novels?title_contains=...` — only Public novels appear
2. **ID Queries** — `GET /novels/{novel_id}` — Unlisted and Public accessible to all; Private and Restricted require contributor status
3. **On Create Checks** — `POST /novels` — Restricted novels with matching alias can trigger collaboration requests (not yet implemented)

**Visibility use cases:**

| Level | Use Case |
|-------|----------|
| Private | Personal projects, sensitive/copyrighted content, WIP translations |
| Restricted | Open to collaboration via alias matching without public exposure (alias system TBD) |
| Unlisted | Shareable via direct link, useful for beta readers or limited sharing |
| Public | Community translations, discoverable in searches |

### Contributor Roles

Each novel has contributors stored in the `novel_contributors` table:

| Role | Permissions |
|------|-------------|
| **owner** | Full control: delete novel, manage contributors, edit chapters, change visibility |
| **editor** | Edit chapters, create revisions, manage labels, cannot change contributors |
| **viewer** | Read-only access to all chapters (including non-public revisions) |

- Novel creator is automatically added as owner
- Multiple owners allowed
- Admins bypass these checks entirely

### Chapter Revision Visibility

Chapter revisions have a `revision_is_public` boolean flag:

- **Public (`true`)** — Visible to all users who have access to the parent novel
- **Private (`false`)** — Visible only to novel contributors

Chapter revisions also have a `revision_is_final` boolean flag. Final revisions are intended to be **immutable** — once marked as final, the revision content should not be modified. This is enforced at the application level, not via database constraints.

> **Note:** The `revision_is_final` flag simplifies labeling (labels attach to revisions, not chapters) but limits flexibility. It may be removed in the future, which would require significant refactoring.

**Access matrix:**

| User Type | Novel Visibility | Revision Public | Access? |
|-----------|-----------------|-----------------|---------|
| Admin | Any | Any | ✅ Yes |
| Contributor | Any | Any | ✅ Yes |
| Regular User | Public/Unlisted | Public | ✅ Yes |
| Regular User | Public/Unlisted | Private | ❌ No |
| Regular User | Private/Restricted | Any | ❌ No |

### Novel Helper Functions

Defined in `backend/src/novels/permissions.py`:

| Helper | Statement Type | Access Level |
|--------|---------------|-------------|
| `novel_mod_access_select` | Select | Public/unlisted, or contributor |
| `novel_mod_access_update` | Update | Owner or editor |
| `chapter_mod_access_select` | Select | Same as novel select (checks parent novel) |
| `chapter_mod_access_insert` | Select (for insert-from-select) | Owner or editor of parent novel |
| `chapter_mod_access_update` | Update | Owner or editor of parent novel |
| `revision_mod_access_select` | Select | Novel access + revision public, or contributor |
| `revision_mod_access_insert` | Select (for insert-from-select) | Owner or editor of parent novel (via chapter) |
| `revision_mod_access_update` | Update | Owner or editor of parent novel |
| `revision_mod_access_delete` | Delete | Owner of parent novel only |

**Not yet implemented:** `novel_mod_access_delete`, `chapter_mod_access_delete`.

---

## Label Group Permissions

Label groups follow a similar contributor model to novels, **but are also constrained by the parent novel's permissions** via cascading checks.

### Label Contributor Roles

Stored in `label_group_contributors` table:

| Role | Permissions |
|------|-------------|
| **owner** | Full control: delete group, manage contributors, edit labels |
| **editor** | Create, edit, delete labels |
| **viewer** | Read-only access to labels |

### Cascading Permission Model

Label permission helpers compose novel/revision permission checks into their own queries. A child resource is only accessible if the user passes **all** ancestor checks.

**Viewing a label group** requires:
1. Access to the parent novel (public/unlisted OR novel contributor)
2. Contributor status in the label group

**Editing a label** requires:
1. Access to the chapter revision (public OR novel contributor)
2. Editor/owner role in the label group

**Creating a label group** requires:
1. Access to the parent novel (uses insert-from-select pattern)
2. Novel ownership is NOT required — any user with novel access can create label groups
3. Creator automatically becomes label group owner

**Example scenario:**
```
Novel: visibility=PUBLIC, user is NOT a novel contributor
Chapter Revision: is_public=FALSE (private draft)
Label Group: user is label group owner

Result: User CANNOT label this revision (lacks novel contributor status for private revision)
```

**Implementation:** `label_group_mod_access_select` first checks novel access by composing `novel_mod_access_select` into a correlated subquery, then checks label group contributor status:

```python
def label_group_mod_access_select[T : Select[tuple[Any, ...]]](
    q : T, current_user : User, only_editors : bool = False
) -> T:
    # Check novel access (parent)
    q_exists_novel = select(Novel.novel_id).where(
        Novel.novel_id == LabelGroup.novel_id
    ).correlate(LabelGroup)
    q_exists_novel = novel_mod_access_select(q_exists_novel, current_user)
    q = q.where(exists(q_exists_novel))

    # Check label group contributor status (child)
    if current_user.user_type != UserType.ADMIN:
        q = q.where(exists(
            select(1).select_from(LabelContributor).where(and_(
                LabelContributor.label_group_id == LabelGroup.label_group_id,
                LabelContributor.user_id == current_user.user_id,
                or_(
                    literal(only_editors is False),
                    LabelContributor.label_contributor_role.in_([LabelRole.OWNER, LabelRole.EDITOR])
                )
            ))
        ))
    return q
```

**`only_editors` parameter:** When `True`, restricts to label groups where the user is an owner or editor, excluding viewer-only access. Used by the filter system to ensure only users with edit rights can apply filters.

For labels specifically, three layers must all pass:
1. Novel access (public/unlisted OR novel contributor)
2. Chapter revision access (public OR novel contributor)
3. Label group access (contributor with appropriate role)

### Label Helper Functions

Defined in `backend/src/labels/permissions.py`:

| Helper | Statement Type | Access Level |
|--------|---------------|-------------|
| `label_group_mod_access_select` | Select | Novel access + label group contributor (supports `only_editors`) |
| `label_group_mod_access_insert` | Select (for insert-from-select) | Novel access (any user with novel access can create) |
| `label_group_mod_access_update` | Update | Novel access + label group owner/editor |
| `label_data_mod_access_select` | Select | Revision access + label group contributor |
| `label_data_mod_access_update` | Update | Revision access + label group owner/editor |
| `label_data_mod_access_insert` | Select (for insert-from-select) | Label group owner/editor + novel access |
| `label_mod_access_insert` | Select (for insert-from-select) | Revision access + label group owner/editor |
| `label_mod_access_update` | Update | Revision access + label group owner/editor |
| `label_mod_access_delete` | Delete | Revision access + label group owner/editor |

**Not yet implemented:** `label_group_mod_access_delete`.

---

## AutoLabel Permissions

AutoLabel access is based purely on **chapter revision visibility** — there are no dedicated label group contributor checks for auto-labels, and no `autolabels/permissions.py` file exists.

The autolabel service has relatively few endpoints, so a dedicated permission module is not yet warranted. Dedicated helpers may be implemented as the service grows.

Current approach:

| Function | Method |
|----------|--------|
| `query_auto_label_by_id` | Manual check: joins to revision, checks `revision_is_public`, raises `InsufficientPermissionsException` if user is not admin and revision is not public |
| `query_auto_labels` | Uses `revision_mod_access_select()` from novels |
| `insert_auto_labels` | Uses `revision_mod_access_select()` on the SELECT portion of an insert-from-select |

See `background-jobs.md` for more details.

---

## Filter Permissions

The filter system does not have its own `permissions.py` because filters do not own any database resources. Filters operate on labels and label data, so they **reuse label and novel permission helpers** directly:

- `label_group_mod_access_select(q, current_user, only_editors=True)` — ensures only editors/owners can apply filters to label groups
- `label_data_mod_access_select` — controls read access to label data during filtering
- `label_data_mod_access_insert` — controls write access when filters copy label data
- `label_mod_access_delete` — controls deletion of labels by filters
- `revision_mod_access_select` — used within individual filter implementations for revision access

Filter permissions cascade through the same **novel → label group → label** stack as regular label operations.

---

## Authorization Patterns


### SELECT (Read)

```python
def query_novel_by_id(db: Session, current_user: User | None, novel_id: int) -> Novel:
    q = select(Novel).where(Novel.novel_id == novel_id)
    q = novel_mod_access_select(q, current_user)
    result = db.execute(q)
    try:
        return result.scalar_one()
    except NoResultFound:
        raise NovelNotFoundException  # Could be missing OR forbidden
```

### UPDATE (Edit)

```python
def modify_novel(db: Session, current_user: User, novel_id: int, updates: dict) -> Novel:
    stmt = update(Novel).where(Novel.novel_id == novel_id).values(**updates)
    stmt = novel_mod_access_update(stmt, current_user)
    stmt = stmt.returning(Novel)
    result = db.execute(stmt)
    db.commit()
    try:
        return result.scalar_one()
    except NoResultFound:
        raise NovelNotFoundException  # Could be missing OR forbidden
```

### INSERT (Create — No Parent)

Resources with no parent requiring permission checks (e.g., novels) just require the user to be logged in. Standard `db.add()` is used:

```python
def insert_novel(db: Session, current_user: User, request: CreateNovel) -> Novel:
    novel = Novel(**request.model_dump())
    db.add(novel)
    db.flush()
    contributor = Contributor(
        contributor_role=Role.OWNER, novel_id=novel.novel_id, user_id=current_user.user_id
    )
    db.add(contributor)
    db.commit()
    return novel
```

### INSERT (Create — With Parent)

Resources with a parent resource use the **insert-from-select** pattern. A `select(literal(...))` query is built with permission WHERE clauses, then fed into `insert(...).from_select(...)`:

```python
def insert_chapter(db: Session, current_user: User, novel_id: int, request: CreateChapter) -> Chapter:
    data = list(request.model_dump().items())
    data.append(('novel_id', novel_id))
    cols = [k for k, _ in data]

    vals = select(*[literal(v) for _, v in data])
    vals = chapter_mod_access_insert(vals, current_user, novel_id)

    stmt = insert(Chapter).from_select(cols, vals).returning(Chapter)
    result = db.execute(stmt)
    result_row = result.scalar_one()  # NoResultFound if permission denied
    db.commit()
    return result_row
```

### DELETE

```python
def remove_chapter_revision(db: Session, current_user: User, revision_id: int) -> None:
    stmt = delete(Revision).where(
        Revision.revision_id == revision_id
    )
    stmt = revision_mod_access_delete(stmt, current_user)
    result = db.execute(stmt)
    db.commit()
    if result.rowcount == 0:
        raise RevisionNotFoundException
```

---

## Security Considerations

### Zero-Knowledge Resource Privacy

**Goal:** Achieve zero-knowledge sharing on resources. A user who does not have access to a resource should not be able to determine whether that resource exists. This is critical because NovelTL may host sensitive, copyrighted, or work-in-progress translations that users explicitly mark as private. Any information leakage — even confirming existence — violates the privacy expectation.

**How this is enforced:**

Permission helpers modify the query itself, so inaccessible resources are simply filtered out of results. A query for a private novel returns the same `NoResultFound` whether the novel doesn't exist or the user lacks access:

```python
# Permission-filtered query — same error for both "not found" and "forbidden"
q = select(Novel).where(Novel.novel_id == novel_id)
q = novel_mod_access_select(q, current_user)
try:
    return db.execute(q).scalar_one()
except NoResultFound:
    raise NovelNotFoundException  # Ambiguous: missing or forbidden
```

This extends through the cascading permission model — child resource helpers always check parent access first, preventing child resources from leaking information about their parents. For example, querying a label group for a private novel returns "label group not found" rather than "novel access denied."

### Guest Access

Some endpoints allow guest access via `get_optional_user()`:
- `GET /novels` — only shows public novels
- `GET /novels/{novel_id}` — only if novel is public/unlisted

Guests are treated as users with no contributor relationships. Permission helpers handle `current_user = None` by filtering to `Visibility.UNLISTED` or above.

### Admin Bypass

Every permission helper returns the unmodified statement for admin users:

```python
if current_user.user_type == UserType.ADMIN:
    return query  # No filters applied
```

**Implications:**
- Admins can SELECT, INSERT, UPDATE, DELETE any resource
- No contributor relationship or visibility restrictions apply
- Requires complete trust in admin users
- No audit trail exists (future enhancement)

---

## Relevant Files

| File | Contents |
|------|----------|
| `backend/src/auth/constants.py` | `UserType` enum |
| `backend/src/auth/models.py` | `User` model |
| `backend/src/auth/dependencies.py` | `get_current_user`, `get_optional_user` |
| `backend/src/novels/constants.py` | `Visibility` enum, `Role` enum |
| `backend/src/novels/models.py` | `Novel`, `Contributor`, `Chapter`, `Revision` models |
| `backend/src/novels/permissions.py` | Novel/chapter/revision permission helpers |
| `backend/src/labels/constants.py` | `LabelRole` enum |
| `backend/src/labels/models.py` | `LabelGroup`, `LabelContributor`, `Label`, `LabelData` models |
| `backend/src/labels/permissions.py` | Label group/label/label data permission helpers |
| `backend/src/exceptions.py` | Permission-related exceptions |

## See Also

- [architecture.md](architecture.md) — Auth service overview
- [database-schema.md](database-schema.md) — Contributor table schemas
- [api-design.md](api-design.md) — How permissions affect API responses
- [conventions.md](conventions.md) — Naming conventions for permission functions
