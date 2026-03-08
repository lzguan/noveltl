# NovelTL Documentation

**Last Updated**: March 7, 2026  
**Status**: Complete

This directory contains technical documentation for the NovelTL project - a collaborative platform for novel translation using Named Entity Recognition (NER) and LLM-assisted workflows.

---

## Table of Contents

1. [Documentation Structure](#documentation-structure)
2. [Document Format Standard](#document-format-standard)
3. [Quick Start](#quick-start)
4. [Migration Notes](#migration-notes)
5. [Contributing to Documentation](#contributing-to-documentation)

---

## Documentation Structure

### Core Architecture
- **[architecture.md](architecture.md)** - System architecture, microservices, tech stack
- **[database-schema.md](database-schema.md)** - Database models, relationships, constraints
- **[api-design.md](api-design.md)** - REST API patterns, authentication, OpenAPI schemas
- **[permissions.md](permissions.md)** - Permission system, visibility levels, contributors

### Features & Implementation
- **[background-jobs.md](background-jobs.md)** - AutoLabel worker system, Redis queues, state machines
- **[filter-system.md](filter-system.md)** - Filter abstraction, 4-phase pipeline, implementations
- **[ui-requirements.md](ui-requirements.md)** - Frontend component specs, UX workflows

### Development
- **[conventions.md](conventions.md)** - Code naming conventions, API patterns
- **[testing.md](testing.md)** - Testing strategy, pytest usage, fixtures

### Reference
- **[GitHub Issues](https://github.com/lzguan/NovelTL_Dev/issues)** - Known bugs, tech debt, future improvements
- **[private_issues.md](private_issues.md)** - Environment-specific troubleshooting
- **[concepts/](concepts/)** - Implementation notes on specific technologies

## Document Format Standard

All documentation files should follow this format:

```markdown
# Document Title

**Last Updated**: YYYY-MM-DD  
**Status**: Complete | Draft | Outdated

Brief introduction paragraph explaining what this document covers and who should read it.

## Table of Contents

[Table of contents here...]

## Main Content Sections

[Your content here...]

## Relevant Files
- `path/to/file.py` - Brief description of what this file does
- `path/to/folder/` - Brief description of folder contents

## See Also
- [Related Doc](related-doc.md) - Brief explanation of relationship
- [Another Doc](another-doc.md) - Brief explanation of relationship
```

### Status Definitions

- **Complete** - Up to date with current implementation
- **Draft** - Work in progress, may be incomplete or change
- **Outdated** - Needs updating, may contain deprecated information

### Updating Documentation

**When to update the "Last Updated" date:**
- ✅ Content changes (new sections, updated explanations, code examples)
- ✅ Significant corrections or clarifications
- ✅ Updated to reflect implementation changes
- ❌ Status field changes only (Complete → Outdated)
- ❌ Minor typo fixes or formatting adjustments
- ❌ Adding cross-references or "See Also" links

**When making significant code changes:**
1. Update the **Last Updated** date to current date (if content changed)
2. Review **Status** - change to Outdated if no longer accurate
3. Update **Relevant Files** section if file paths changed
4. Add migration notes if behavior changed

## Quick Start

**New to the project?** Read in this order:
1. [architecture.md](architecture.md) - Understand the overall system
2. [database-schema.md](database-schema.md) - Learn the data models
3. [conventions.md](conventions.md) - Coding standards
4. [api-design.md](api-design.md) - API patterns

**Working on features?** Check:
- [background-jobs.md](background-jobs.md) - For AutoLabel/worker tasks
- [filter-system.md](filter-system.md) - For label filtering/processing
- [permissions.md](permissions.md) - For access control

**Frontend development?** See:
- [ui-requirements.md](ui-requirements.md) - Component specifications
- [api-design.md](api-design.md) - Backend API contracts

## Migration Notes

### March 5, 2026 - Documentation Reorganization

The documentation was reorganized for better separation of concerns:

**Old → New Mapping:**
- `DESIGN.md` → Split into:
  - `architecture.md` (service overview, motivation)
  - `database-schema.md` (database models)
  - `permissions.md` (access control)
  - `background-jobs.md` (AutoLabel system)
  
- `requirements.md` → Split into:
  - `filter-system.md` (filter abstraction and API)
  - `ui-requirements.md` (frontend specs)

- `tests.md` → Expanded into `testing.md`

**Deprecated Files:**
- `DESIGN.md` - Marked as outdated, refer to new split documents
- `requirements.md` - Marked as outdated, refer to new split documents

## Contributing to Documentation

When adding new documentation:
1. Follow the standard format above
2. Add entry to this README under appropriate section
3. Include cross-references in "See Also" sections
4. Update related documents' "See Also" sections to link back

When you notice outdated docs:
1. Change status to "Outdated"
2. Add a note at the top explaining what's changed
3. Create a [GitHub Issue](https://github.com/lzguan/NovelTL_Dev/issues) to track the update

## Relevant Files
- `docs/` - This directory
- `backend/src/` - Backend implementation
- `frontend/src/` - Frontend implementation
- `compose.yaml` - Docker service definitions

## See Also
- [conventions.md](conventions.md) - Coding standards referenced throughout
- [GitHub Issues](https://github.com/lzguan/NovelTL_Dev/issues) - Known issues and planned improvements
- Project root README (if exists) - General project overview
