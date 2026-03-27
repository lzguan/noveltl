---
name: audit-documentation
description: Instructions for auditing and updating project documentation. Use when user asks for help with documentation review, updating, or writing new docs.
---

# Documentation Audit Guide

## Audit Depth

When the user requests a documentation audit, determine the appropriate depth. If the user doesn't specify, default to **standard**. You can ask the user which depth they prefer.

- **Quick** — Style compliance only (format, required sections, headers). No source code reads. Fast.
- **Standard** — Style + verify `Relevant Files` paths exist + cross-document consistency checks.
- **Deep** — Full source code verification against all documentation claims. Thorough but expensive.

## Instructions

### Step 1: Read the documentation style guide

First, take note of the project's folder structure:

```
NovelTL_Dev/
├── backend/
├── frontend/
├── docs/
│   ├── README.md
│   ├── conventions.md
│   ├── other doc files...
```

Read the `docs/README.md` file to understand the overall documentation structure, purpose of each doc, and how they relate to each other. This will help you navigate the docs effectively.
Read the `docs/conventions.md` file to understand the coding and documentation conventions that should be followed in all documentation. This includes formatting, naming conventions, and guidelines for writing clear and consistent documentation.
Make a summary of the key points from the style guide that you will use to evaluate the documentation. This includes:
- The required sections for each doc (e.g., "Last Updated", "Status", "Relevant Files", "See Also")
- The expected content and format for each section
- The conventions for code examples (e.g., naming, formatting)
- The process for updating documentation (when to update "Last Updated", how to handle significant code changes, etc.)

### Step 2: Identify the relevant documentation

Based on the user's request, determine which documentation files are relevant. For example, if they ask about testing practices, focus on `docs/backend-testing.md`. If they ask about API design, focus on `docs/api-design.md`. The `conventions.md` file is always relevant. Make a list of the relevant files to review in detail.

**Deprecation handling:** If a document contains a deprecation notice, it is invalid and does not need to be audited. Skip the audit and confirm that the documentation is deprecated. However, verify that the replacement documents listed in the deprecation notice actually exist and link back to (or cover) the deprecated content. This ensures the migration is complete in both directions.

### Step 3: Review that the relevant documentation follows the style guide

Check that the relevant documentation follows the style guide outlined in `docs/README.md`. Use the summary you made in Step 1 to evaluate each section of the documentation.

**Incomplete content detection:** Scan each document for signs of unfinished content:
- Truncated sections (text that cuts off mid-sentence or mid-thought)
- Placeholder text (e.g., "TODO", "TBD", "WIP", "Test addition", "Lorem ipsum")
- Empty sections (headers with no content below them)
- Bullet points that trail off or are clearly incomplete

If a document has incomplete content, flag it and recommend that its `Status` be set to `Draft` if it isn't already.

Generate a list of specific style issues that need to be addressed to bring the documentation in line with the style guide.

### Step 4: Verify Relevant Files paths exist

For each document's `## Relevant Files` section, verify that every listed file or directory path actually exists in the workspace. Run a quick check (e.g., `ls` or file search) for each path. Flag any paths that no longer exist — these indicate stale references from renames, moves, or deletions.

Also check if any file paths mentioned _within the document body_ (not just the Relevant Files section) point to files that no longer exist.

_(Skip this step for **quick** audits.)_

### Step 5: Review that the content is accurate and up to date

For each document, make a list of relevant source code files. This list can be found in the "Relevant Files" section of the documentation, or you can identify them based on your knowledge of the codebase and the topic of the documentation. For example, if reviewing `docs/backend-testing.md`, relevant files might include `backend/tests/conftest.py` and `backend/tests/fixtures/password_hash.py`. If you identify any additional relevant files that are not listed in the documentation, add them to your list. You can dynamically update this list as you review the documentation and identify more relevant files.

For each relevant documentation file, read the corresponding relevant source code files. Review the content and compare it against the current state of the codebase. Check for any discrepancies, outdated information, or missing details that should be included to accurately reflect the current implementation and best practices. Pay special attention to any sections that describe architecture decisions, design patterns, or specific implementation details, as these are more likely to become outdated as the code evolves.

**Cross-document consistency:** When a factual claim appears in a document (e.g., "passwords are hashed with bcrypt"), search for the same topic in other docs. If two documents make contradictory claims about the same thing, flag the inconsistency. At least one of them is wrong — verify against source code to determine which.

Generate a list of specific updates needed to bring the documentation up to date and ensure it accurately reflects the current state of the codebase and best practices.

_(For **quick** and **standard** audits, skip the source code reading portion of this step. Standard audits should still perform the cross-document consistency check.)_

### Step 6: Review that code examples follow the code conventions
Check that any code examples in the documentation follow the coding conventions outlined in `docs/conventions.md`. This includes but is not limited to:
- Proper naming conventions (e.g., `snake_case` for Python variables and functions, `kebab-case` for URLs, etc.)
- Consistent formatting (e.g., indentation, spacing)
- Use of type annotations where appropriate

Generate a list of specific code convention issues that need to be addressed in the documentation's code examples.

_(Skip this step for **quick** audits.)_

### Step 7: Check Last Updated date plausibility

For each document, compare the `Last Updated` date against the file's actual last modification time (via `git log -1 --format="%ai" -- <filepath>` or similar). If the git history shows the file was modified significantly more recently (or less recently) than the stated date, flag it. This catches cases where code-driven doc updates forgot to bump the date, or where the date was bumped without meaningful content changes.

_(Skip this step for **quick** audits.)_

### Step 8: Compile a comprehensive list of issues and updates needed
Combine the lists generated in the previous steps into a single comprehensive list of issues that need to be addressed to bring the documentation in line with the style guide, ensure accuracy, and follow code conventions. This list should be organized by category (style issues, content updates, code convention issues, stale file references, cross-document inconsistencies) and should include specific details about what needs to be changed and why.

### Step 9: Provide recommendations for updating the documentation
Based on the comprehensive list of issues, provide clear and actionable recommendations for updating the documentation. This should include:
- A prioritized list of updates, starting with the most critical issues (e.g., inaccuracies, cross-document contradictions, or outdated information) and followed by stale file references, style issues, and code convention issues.
- Specific instructions for how to address each issue, including what changes need to be made and any relevant guidelines from the style guide.
