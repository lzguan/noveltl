# Permissions System

**Last Updated**: March 5, 2026  
**Status**: Complete

This document describes the access control and permission system for NovelTL, including visibility levels, contributor roles, and authorization patterns.

## Overview

NovelTL uses a fine-grained permission system based on:
1. **User Types** - Admin vs. regular user
2. **Visibility Levels** - Novel/label group exposure control
3. **Contributors** - Role-based access to specific resources
4. **Request Types** - Different permissions for search, ID query, and creation

## Design Rationale

### Why Permission Helper Functions?

**Problem:** Scattering permission logic across service functions leads to:
- **Inconsistent checks** - Different developers implement access control differently
- **SQL injection risks** - Manual WHERE clause construction prone to errors
- **Maintenance burden** - Changing permission rules requires updating dozens of functions
- **Missing checks** - Easy to forget permission filters in new queries
- **Difficult auditing** - No single place to review all access control logic

**Solution:** Centralized permission helper functions that modify SQL queries.

### What Are Permission Helper Functions?

Permission helpers are functions that take a SQLAlchemy query/statement and return a modified version with permission filters applied:

```python
def resource_mod_access_select(query: Select, current_user: User | None) -> Select:
    """
    Takes a SELECT query and adds WHERE clauses to filter results based on:
    - User type (admin bypasses all checks)
    - Resource visibility level
    - Contributor relationship with the user
    
    Returns the modified query that only selects accessible resources.
    """
```

**Key Characteristics:**
- **Input:** SQLAlchemy Select/Update/Delete statement + current user
- **Output:** Modified statement with permission WHERE clauses added
- **Naming Convention:** `{resource}_mod_access_{operation}` (e.g., `novel_mod_access_select`, `label_mod_access_update`)
- **Operation Types:**
  - `*_select` - Read access (viewing resources)
  - `*_insert` - Create access (verifying parent resource access)
  - `*_update` - Edit access (modifying resources)
  - `*_delete` - Delete access (removing resources, usually owner-only)

**How They Work:**

1. Check if user is admin → return unmodified query (bypass)
2. Check if user is guest (`None`) → filter to public/unlisted only
3. For regular users → add OR conditions:
   - Resource is public/unlisted, OR
   - User is a contributor with appropriate role

The SQL is built using SQLAlchemy's query builder, ensuring type safety and preventing injection attacks.

### Example Comparison

```python
# ❌ BAD: Manual permission checks scattered everywhere
def query_novel_by_id(db, current_user, novel_id):
    novel = db.get(Novel, novel_id)
    if not novel:
        raise NotFoundException
    
    # Different developer might forget this check!
    if novel.visibility < Visibility.UNLISTED:
        # What if we forget to check contributor status?
        if current_user is None:
            raise PermissionException
        # Is this the right SQL? Hard to verify!
        contributor = db.execute(select(Contributor).where(...)).first()
        if not contributor:
            raise PermissionException
    
    return novel

# ✅ GOOD: Centralized helper ensures consistent behavior
def query_novel_by_id(db, current_user, novel_id):
    q = select(Novel).where(Novel.novel_id == novel_id)
    q = novel_mod_access_select(q, current_user)  # Single source of truth
    try:
        return db.execute(q).scalar_one()
    except NoResultFound:
        raise NotFoundException
```

**Benefits:**
1. **Single Source of Truth** - All permission logic for novels lives in `novel_mod_access_select()`
2. **Correctness** - SQL is constructed by tested helper functions, not repetitive manual code
3. **Consistency** - Same rules applied everywhere, no edge cases from copy-paste errors
4. **Maintainability** - Change visibility rules in one place, all queries update automatically
5. **Type Safety** - Generic type parameters prevent passing wrong query types to helpers
6. **Security** - Harder to accidentally bypass permission checks (query won't compile without them)

### Enforcement Pattern

Service layer functions **always** apply permission helpers before executing queries:

```python
# Pattern: apply helper → execute → handle not found
q = select(Resource).where(Resource.id == resource_id)
q = resource_mod_access_select(q, current_user)  # ← Mandatory
result = db.execute(q)
return result.scalar_one()
```

**Code Review Checklist:**
- ✅ Does every SELECT query use a `*_mod_access_select()` helper?
- ✅ Does every UPDATE query use a `*_mod_access_update()` helper?
- ✅ Does every INSERT verify parent access with `*_mod_access_insert()`?
- ✅ Does every DELETE use a `*_mod_access_delete()` helper?

## User Types

### Admin

**Admins bypass ALL permission checks in the current implementation.**

Every permission helper function checks `if current_user.user_type == UserType.ADMIN` and returns the unfiltered query/statement if true. This means:

- ✅ Full access to all resources regardless of visibility
- ✅ Can view/modify/delete any novel, label group, or chapter
- ✅ Can manage any user's data
- ✅ No contributor relationship required
- ✅ Bypasses all role-based restrictions (owner/editor/viewer)

**Trade-off:** This simplifies administrative operations but requires complete trust in admin users. There is no audit trail or fine-grained admin permissions.

### User
- Restricted to resources they own or contribute to
- Subject to visibility level restrictions
- Cannot access other users' private resources
- Must have appropriate contributor role for modifications

**Note:** User type is set at account creation and stored in `users.user_type`.

## Novel Permissions

### Visibility Levels

Novels have four visibility levels (stored as integers in `novels.novel_visibility` with mapping defined using a python `IntEnum`):

| Level | Name | Search | ID Query | Create Check | Description |
|-------|------|--------|----------|--------------|-------------|
| 0 | **Private** | ❌ | Contributors only | ❌ | Only contributors can access |
| 1 | **Restricted** | ❌ | Contributors only | Alias match → request | Like private, but alias matching enabled |
| 2 | **Unlisted** | ❌ | ✅ Anyone | ✅ Anyone | Accessible by direct link, hidden from search |
| 3 | **Public** | ✅ Anyone | ✅ Anyone | ✅ Anyone | Fully public |

#### Request Type Definitions

1. **Search/Filter Queries** - User searches for a novel by name or properties
   - `GET /novels?title_contains=...`
   - Only Public novels appear in results

2. **ID Queries** - User requests a novel by its unique ID
   - `GET /novels/{novel_id}`
   - Unlisted and Public novels accessible to all
   - Private and Restricted require contributor status

3. **On Create Checks** - User creates a novel that might duplicate existing one
   - `POST /novels`
   - Restricted novels with matching alias can send collaboration request (TBD)
   - Currently not fully implemented

#### Visibility Level Use Cases

**Private (0):**
- Personal projects not ready for sharing
- Sensitive or copyrighted content
- Work-in-progress translations

**Restricted (1):**
- Open to collaboration with users working on same source material
- Allows discovery via alias matching without public exposure
- **Note:** Alias system not yet implemented

**Unlisted (2):**
- Shareable via direct link
- Not indexed in public searches
- Useful for beta readers or limited sharing

**Public (3):**
- Open to all users
- Discoverable in searches
- Community translations

### Contributor Roles

Each novel has a list of contributors with specific roles (stored in `novel_contributors` table).

| Role | Permissions |
|------|-------------|
| **owner** | Full control: delete novel, manage contributors, edit chapters, change visibility |
| **editor** | Edit chapters, create revisions, manage labels, cannot change contributors |
| **viewer** | Read-only access to all chapters (including non-public revisions) |

**Key Points:**
- Novel creator is automatically added as owner
- Multiple owners allowed
- Admins bypass these checks entirely

### Chapter Revision Visibility

Chapter revisions have a `raw_chapter_revision_public` boolean flag:

- **Public (`true`)** - Visible to all users with novel access
- **Private (`false`)** - Visible only to novel contributors

**Access Matrix:**

| User Type | Novel Visibility | Revision Public | Access? |
|-----------|-----------------|-----------------|---------|
| Admin | Any | Any | ✅ Yes |
| Contributor | Any | Any | ✅ Yes |
| Regular User | Public/Unlisted | Public | ✅ Yes |
| Regular User | Public/Unlisted | Private | ❌ No |
| Regular User | Private/Restricted | Any | ❌ No |

### Authorization Helpers

Permission checks are implemented using query modification functions in `backend/src/novels/permissions.py`:

```python
def novel_mod_access_select(query: Select, current_user: User | None) -> Select:
    """Filters SELECT query to only novels user can view"""
    if current_user is None:
        # Guest users: only unlisted and public
        return query.where(Novel.novel_visibility >= Visibility.UNLISTED)
    elif current_user.user_type == UserType.ADMIN:
        return query  # Admins bypass ALL checks
    else:
        # Regular users: public/unlisted OR contributor
        return query.where(or_(
            Novel.novel_visibility >= Visibility.UNLISTED,
            exists(select(1).from(Contributor).where(
                Contributor.novel_id == Novel.novel_id,
                Contributor.user_id == current_user.user_id
            ))
        ))

def novel_mod_access_update(stmt: Update, current_user: User) -> Update:
    """Filters UPDATE statement to only novels user can edit"""
    if current_user.user_type == UserType.ADMIN:
        return stmt  # Admins bypass ALL checks
    else:
        # Regular users: must be owner or editor
        return stmt.where(exists(select(1).from(Contributor).where(
            Contributor.novel_id == Novel.novel_id,
            Contributor.user_id == current_user.user_id,
            Contributor.contributor_role.in_([Role.OWNER, Role.EDITOR])
        )))
```

**Available Helper Types:**
- `*_mod_access_select` - Filter SELECT queries (read access)
- `*_mod_access_insert` - Filter INSERT FROM SELECT statements (create access)
- `*_mod_access_update` - Filter UPDATE statements (edit access)
- `*_mod_access_delete` - Filter DELETE statements (delete access, owners only)

## Label Group Permissions

Label groups follow a similar permission model to novels, **but are also constrained by the parent novel's permissions**.

### Contributor Roles

Stored in `label_group_contributors` table:

| Role | Permissions |
|------|-------------|
| **owner** | Full control: delete group, manage contributors, edit labels |
| **editor** | Create, edit, delete labels |
| **viewer** | Read-only access to labels |

### Interaction with Novel Permissions

**Label groups inherit restrictions from their parent novel:**

1. **Viewing Labels**
   - User must have **both**:
     - Access to the novel (public/unlisted OR novel contributor)
     - Access to the label group (label group contributor)
   - Implementation: `label_group_mod_access_select()` first checks novel access via `novel_mod_access_select()`

2. **Editing Labels**
   - User must have **both**:
     - Access to the chapter revision (public revision OR novel contributor)
     - Editor/owner role in the label group
   - This prevents labeling private chapter revisions unless user is a novel contributor

3. **Creating Label Groups**
   - User must have access to the novel (checks novel visibility)
   - Novel ownership is NOT required (any user with novel access can create label groups)
   - Creator automatically becomes label group owner

**Example Scenario:**
```
Novel: visibility=PUBLIC, user is NOT a contributor
Chapter Revision: is_public=FALSE (private draft)
Label Group: user is owner

Result: User CANNOT label this revision (lacks novel contributor status)
```

### Implementation Details

**How Novel Permissions Are Enforced:**

Label permission helpers enforce novel access by composing novel permission checks into their queries. This creates a **cascading permission model** where child resources inherit parent restrictions.

```python
def label_group_mod_access_select(query: Select, current_user: User) -> Select:
    """Filter label groups by both novel access AND label group contributor status"""
    
    # Step 1: Check novel access first (parent resource)
    novel_access_check = select(Novel.novel_id).where(
        Novel.novel_id == LabelGroup.novel_id
    ).correlate(LabelGroup)
    novel_access_check = novel_mod_access_select(novel_access_check, current_user)
    query = query.where(exists(novel_access_check))
    
    # Step 2: Check label group contributor status (child resource)
    if current_user.user_type != UserType.ADMIN:
        query = query.where(exists(
            select(1).from_table(LabelContributor).where(
                LabelContributor.label_group_id == LabelGroup.label_group_id,
                LabelContributor.user_id == current_user.user_id
            )
        ))
    
    return query
```

**Key Implementation Patterns:**

1. **Parent-First Checking**
   - Novel access verified before label group access
   - Uses subquery with `exists()` for efficient checking
   - `correlate()` links parent table to outer query

2. **Composition of Helpers**
   - `label_group_mod_access_select()` calls `novel_mod_access_select()`
   - `label_data_mod_access_select()` calls both `raw_chapter_revision_mod_access_select()` AND checks label group contributors
   - `label_mod_access_update()` checks revision access AND label group editor role

3. **Dual Filter Strategy**
   ```sql
   -- For labels, both conditions must be satisfied:
   WHERE exists(
       -- Condition 1: Can user access the chapter revision?
       SELECT 1 FROM raw_chapter_revisions 
       JOIN raw_chapters ON ... 
       JOIN novels ON ...
       WHERE (novel public/unlisted OR user is novel contributor)
         AND (revision public OR user is novel contributor)
   )
   AND exists(
       # Condition 2: Is user a label group contributor?
       SELECT 1 FROM label_group_contributors
       WHERE user_id = current_user.user_id
         AND label_contributor_role IN ('owner', 'editor')
   )
   ```

**Result:** A label is only accessible if user has access to:
1. The novel (public/unlisted OR contributor)
2. The chapter revision (public OR novel contributor)  
3. The label group (contributor with appropriate role)

All three layers must pass for access to be granted.

### Public Editability (Future)

**Planned but not yet implemented:**

Label groups will support a `publicly_editable` flag:
- When `true`, any user can contribute labels to the group
- Useful for community labeling projects
- Requires `novel` to also be public
- Individual label `label_dirty` flag tracks manual edits

## Authorization Flow

### 1. Authentication

```
User Request
    → Extract JWT from Authorization header
    → Validate JWT signature and expiration
    → Extract user_id from JWT claims
    → Query User from database
    → Attach User to request context
```

Implemented in `backend/src/auth/dependencies.py`:
- `get_current_user()` - Requires valid JWT, raises 401 if missing
- `get_optional_user()` - Returns User or None, allows guest access

### 2. Authorization

**Service Layer Responsibilities:**
- Apply permission filters to queries using `*_mod_access_*` helpers
- Raise explicit exceptions for forbidden actions
- Use helper functions from `permissions.py`
- Convert permission errors to `NotFoundException` (information disclosure prevention)

**Router Layer Responsibilities:**
- Catch permission exceptions
- Return appropriate HTTP status codes (403 Forbidden, 404 Not Found)
- Handle authentication errors (401 Unauthorized)

### Usage Examples

#### SELECT (Read Access)

```python
# Service layer
def query_novel_by_id(db: Session, current_user: User | None, novel_id: int) -> Novel:
    q = select(Novel).where(Novel.novel_id == novel_id)
    q = novel_mod_access_select(q, current_user)  # Apply permissions
    result = db.execute(q)
    try:
        return result.scalar_one()
    except NoResultFound:
        raise NovelNotFoundException  # Permission denied looks like "not found"

# Router layer
@router.get("/novels/{novel_id}")
def read_novel(novel_id: int, current_user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    try:
        novel = query_novel_by_id(db, current_user, novel_id)
        return novel
    except NovelNotFoundException:
        raise HTTPException(status_code=404, detail="Novel not found")
```

#### UPDATE (Edit Access)

```python
# Service layer
def modify_novel(db: Session, current_user: User, novel_id: int, updates: dict) -> None:
    stmt = update(Novel).where(Novel.novel_id == novel_id).values(**updates)
    stmt = novel_mod_access_update(stmt, current_user)  # Requires editor/owner
    result = db.execute(stmt)
    db.commit()
    if result.rowcount == 0:
        # Either doesn't exist or user lacks permission
        raise NovelNotFoundException

# Router layer
@router.patch("/novels/{novel_id}")
def update_novel(novel_id: int, updates: UpdateNovel, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        modify_novel(db, current_user, novel_id, updates.model_dump())
        return {"status": "success"}
    except NovelNotFoundException:
        raise HTTPException(status_code=404, detail="Novel not found")
```

#### INSERT FROM SELECT (Create with Parent Access Check)

**Special Case:** INSERT operations often need to verify access to a parent resource without adding it to the inserted data.

```python
# Service layer
def insert_label_group(db: Session, current_user: User, novel_id: int, name: str) -> LabelGroup:
    # Verify novel access using a SELECT statement
    verify_query = select(literal(1))
    verify_query = label_group_mod_access_insert(verify_query, current_user, novel_id)
    result = db.execute(verify_query)
    if result.scalar_one_or_none() is None:
        raise NovelNotFoundException  # No access to novel
    
    # Create label group
    label_group = LabelGroup(novel_id=novel_id, label_group_name=name)
    db.add(label_group)
    db.flush()
    
    # Add creator as owner
    contributor = LabelContributor(
        label_group_id=label_group.label_group_id,
        user_id=current_user.user_id,
        label_contributor_role=LabelRole.OWNER
    )
    db.add(contributor)
    db.commit()
    return label_group
```

**Why SELECT for INSERT?**
- Cannot directly filter INSERT statements on parent resources
- Need to verify parent access before creating child
- `*_mod_access_insert()` helpers take a SELECT statement + parent ID
- Returns filtered SELECT that only succeeds if user has access to parent

#### DELETE (Owner-Only Access)

```python
# Service layer
def remove_label(db: Session, current_user: User, label_id: int) -> None:
    stmt = delete(Label).where(Label.label_id == label_id)
    stmt = label_mod_access_delete(stmt, current_user)  # Filters by owner role
    result = db.execute(stmt)
    db.commit()
    if result.rowcount == 0:
        raise LabelNotFoundException

# Router layer
@router.delete("/labels/{label_id}")
def delete_label(label_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        remove_label(db, current_user, label_id)
        return {"status": "success"}
    except LabelNotFoundException:
        raise HTTPException(status_code=404, detail="Label not found")
```

## Security Considerations

### Information Disclosure Prevention

**Problem:** Permission errors can leak information about private resources.

#### 1. Resource Existence Disclosure

**Vulnerability:** Returning `403 Forbidden` reveals that a resource exists.

```python
# BAD: Reveals existence
def get_novel(db, current_user, novel_id):
    novel = db.get(Novel, novel_id)
    if not novel:
        raise HTTPException(404, "Novel not found")
    if not has_access(current_user, novel):
        raise HTTPException(403, "Access denied")  # ❌ User knows novel exists!
```

**Solution:** Use permission-filtered queries so inaccessible resources look non-existent.

```python
# GOOD: Same error for both cases
def get_novel(db, current_user, novel_id):
    q = select(Novel).where(Novel.novel_id == novel_id)
    q = novel_mod_access_select(q, current_user)  # Filter by permissions
    try:
        return db.execute(q).scalar_one()
    except NoResultFound:
        raise NovelNotFoundException  # ✅ Could be missing OR forbidden
```

**Result:** User cannot distinguish between:
- Resource doesn't exist
- Resource exists but user lacks permission

#### 2. Cascade Permission Leaks

**Vulnerability:** Child resources revealing parent resource information.

```python
# Example: Label group for private novel
Label Group ID 42 exists
Novel ID 10 is PRIVATE, user not a contributor

Query: GET /label-groups/42
Bad Response: "Novel access denied" (reveals novel exists)
Good Response: "Label group not found" (ambiguous)
```

**Solution:** All `*_mod_access_*` helpers for child resources check parent access first.

```python
def label_group_mod_access_select(query, current_user):
    # First check: can user access the parent novel?
    novel_check = select(Novel.novel_id).where(Novel.novel_id == LabelGroup.novel_id)
    novel_check = novel_mod_access_select(novel_check, current_user)
    query = query.where(exists(novel_check))
    
    # Second check: is user a label group contributor?
    # ... contributor check ...
    return query
```

### Guest Access

Some endpoints allow guest access (`get_optional_user()`):
- `GET /novels` - Only shows public novels
- `GET /novels/{novel_id}` - Only if novel is public/unlisted

Guests are treated as users with no contributor relationships.

### Admin Bypass

**Admins bypass ALL permission checks** in every helper function:

```python
# Every permission helper starts with this
def novel_mod_access_select(query, current_user):
    if current_user is None:
        # Guest logic...
    elif current_user.user_type == UserType.ADMIN:
        return query  # ✅ Admins bypass ALL filters
    else:
        # Regular user logic...
```

**Implications:**
- Admins can SELECT, INSERT, UPDATE, DELETE any resource
- No contributor relationship needed
- No visibility level restrictions
- No role-based restrictions (owner/editor/viewer)

**Security Considerations:**
- No audit trail for admin actions (future enhancement needed)
- Admins can access/modify sensitive user data
- Requires complete trust in admin users
- Consider implementing admin activity logging

## Permission Patterns

### Creating Resources

**Pattern:** Verify parent access with SELECT, then create child with automatic ownership

```python
def insert_label_group(db: Session, current_user: User, novel_id: int, name: str) -> LabelGroup:
    # Step 1: Verify access to parent novel using INSERT helper
    verify_query = select(literal(1))
    verify_query = label_group_mod_access_insert(verify_query, current_user, novel_id)
    
    # Execute verification - will return None if no access
    result = db.execute(verify_query)
    if result.scalar_one_or_none() is None:
        raise NovelNotFoundException  # Looks like novel doesn't exist
    
    # Step 2: Create the label group
    label_group = LabelGroup(novel_id=novel_id, label_group_name=name)
    db.add(label_group)
    db.flush()  # Get label_group_id
    
    # Step 3: Grant creator ownership
    contributor = LabelContributor(
        label_group_id=label_group.label_group_id,
        user_id=current_user.user_id,
        label_contributor_role=LabelRole.OWNER
    )
    db.add(contributor)
    db.commit()
    return label_group
```

**Why use `*_mod_access_insert` helpers?**
- INSERT statements cannot be directly filtered on parent resources
- Need to verify parent access before creating child resource
- Helper takes a SELECT statement + parent resource ID
- Returns filtered SELECT query that only succeeds if user has access to parent
- Prevents information disclosure about parent existence/accessibility

### Updating Resources

**Pattern:** Use UPDATE helper to filter by owner/editor role

```python
def modify_novel(db: Session, current_user: User, novel_id: int, updates: dict) -> None:
    stmt = update(Novel).where(Novel.novel_id == novel_id).values(**updates)
    stmt = novel_mod_access_update(stmt, current_user)  # Filters to owner/editor only
    
    result = db.execute(stmt)
    db.commit()
    
    if result.rowcount == 0:
        # Either novel doesn't exist OR user lacks permission
        raise NovelNotFoundException  # Information disclosure prevention
```

**Key Point:** `rowcount == 0` is ambiguous - could mean resource doesn't exist or user lacks permission.

### Deleting Resources

**Pattern:** Use DELETE helper to filter by owner role (most restrictive)

```python
def remove_chapter_revision(db: Session, current_user: User, revision_id: int) -> None:
    stmt = delete(RawChapterRevision).where(
        RawChapterRevision.raw_chapter_revision_id == revision_id
    )
    stmt = raw_chapter_revision_mod_access_delete(stmt, current_user)  # Owner-only
    
    result = db.execute(stmt)
    db.commit()
    
    if result.rowcount == 0:
        raise RawChapterRevisionNotFoundException
```

**Delete Helpers:**
- `raw_chapter_revision_mod_access_delete()` - Requires owner role in parent novel
- `label_mod_access_delete()` - Requires owner/editor role in label group
- Delete operations are typically more restrictive than edits

## Future Enhancements

### Planned Features

1. **Alias System for Restricted Novels**
   - Novels can have multiple aliases (e.g., Chinese title, English title)
   - When user creates novel, check for matching aliases
   - Send collaboration request to owners of matching novels
   - Reduces duplicate translation efforts

2. **Publicly Editable Label Groups**
   - Community-contributed labels
   - Moderation system
   - Track contributor history per label

### Other Ideas (by Claude)

3. **Role-Based API Tokens**
   - Allow programmatic access with scoped permissions
   - Service accounts for automation

4. **Audit Logging**
   - Track who accessed/modified what
   - Compliance and debugging

5. **Permission Delegation**
   - Temporary access grants
   - Time-limited contributor roles

## Relevant Files

- `backend/src/auth/models.py` - User model, UserType enum
- `backend/src/auth/dependencies.py` - Authentication dependencies
- `backend/src/novels/models.py` - Contributor model, Role enum, Visibility enum
- `backend/src/novels/permissions.py` - Novel permission helpers
- `backend/src/labels/models.py` - LabelContributor model, LabelRole enum
- `backend/src/labels/permissions.py` - Label permission helpers
- `backend/src/exceptions.py` - Permission-related exceptions

## See Also

- [architecture.md](architecture.md) - Auth service overview
- [database-schema.md](database-schema.md) - Contributor table schemas
- [api-design.md](api-design.md) - How permissions affect API responses
- [conventions.md](conventions.md) - Naming conventions for permission functions
