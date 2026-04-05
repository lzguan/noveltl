---
name: write-documentation
description: Use when writing or updating documentation files in docs/. Enforces project formatting standards, required sections, and validates file references. Use proactively whenever creating or modifying docs/*.md files.
---

# Documentation Writing Agent

When writing or updating any file in `docs/`, follow these rules. Read `docs/README.md` and `docs/conventions.md` first if you haven't already in this conversation.

## Required Format

Every doc file must have these sections in this order:

```markdown
# Document Title

**Last Updated**: Month DD, YYYY
**Status**: Complete | Draft | Outdated

Brief intro paragraph: what this doc covers and who should read it.

---

## Table of Contents

[numbered list of sections]

---

## [Main content sections...]

## Relevant Files
- `path/to/file.py` - Brief description

## See Also
- [Related Doc](related-doc.md) - Brief explanation
```

## Checklist

Before finishing any doc write or update, verify all of the following:

1. **Status** is one of exactly: `Complete`, `Draft`, `Outdated`
   - Use `Draft` if the feature described is not yet implemented
   - Use `Outdated` if the doc describes something that has since changed
   - Use `Complete` only if the doc accurately reflects current implementation

2. **Last Updated** uses `Month DD, YYYY` format (e.g., `March 21, 2026`)
   - Update the date only if you changed content (new sections, corrections, updated explanations)
   - Do NOT update the date for: status-only changes, typo fixes, formatting, adding See Also links

3. **Intro paragraph** exists between Status and Table of Contents

4. **Table of Contents** exists with numbered entries

5. **Relevant Files** section exists — every path listed must be verified to exist in the repo (use Glob to check). Do not list paths that don't exist.

6. **See Also** section exists with links to related docs. Verify linked docs exist.

7. **Cross-references**: if you mention a concept documented elsewhere, link to it. If another doc should link back to this one, update its See Also section too.

8. **No stale names**: after model/table/function renames, grep the doc for old names before finishing. Common past renames:
   - `RawChapter` → `Chapter`
   - `RawChapterRevision` → `Revision` → removed (collapsed into `Chapter`)
   - `raw_chapter_*` → `chapter_*`
   - `Revision` → removed (metadata merged into `Chapter`)
   - `RevisionText` → `ChapterContent`
   - `revision_id` → `chapter_id` (where it referred to revision metadata)
   - `revision_text_id` → `chapter_content_id`
   - `revision_text_content` → `chapter_content_text`
   - `revision_text_version` → `chapter_content_version`
   - `Contributor` → `NovelContributor`
   - `revision_is_primary` / `revision_is_public` → removed (replaced by `chapter_is_public` on `Chapter`)

## Code Examples

- Python: `snake_case` for variables/functions, `PascalCase` for classes
- URLs: `kebab-case` for path segments, `snake_case` for path params
- JSON keys: `snake_case`
- Frontend TypeScript: `camelCase` for variables/functions, `PascalCase` for types/components
- Include type annotations in Python examples

## When Updating Existing Docs

1. Read the full doc first
2. Preserve existing structure — don't reorganize unless asked
3. If the doc has a deprecation notice, do not audit it — just verify replacement docs exist
4. After editing, re-verify Relevant Files paths still exist
