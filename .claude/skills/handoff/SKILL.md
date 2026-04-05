---
name: handoff
description: Generate a session handoff file capturing current state, progress, and next steps so the next conversation can resume without context loss. Use at end of session or when context is running low.
---

# Session Handoff

Generate a handoff file that captures the current session's state so the next conversation can pick up seamlessly.

## When to use

- User invokes `/handoff`
- Context is running low (~10% remaining)
- Before ending a session with in-progress work

## Process

### Step 1: Gather live state

Collect the following automatically:

```bash
# Current branch and status
git branch --show-current
git status --short

# Recent commits on this branch (since diverging from master)
git log master..HEAD --oneline 2>/dev/null || git log -5 --oneline

# Uncommitted changes summary
git diff --stat
git diff --cached --stat
```

### Step 2: Build the handoff file

Write to `.claude/handoff.md` (overwrite previous — only the latest matters):

```markdown
# Session Handoff

**Date:** YYYY-MM-DD
**Branch:** {branch}

## What was accomplished this session
- {bullet points of completed work}

## Current state
- **Uncommitted changes:** {summary of git diff, or "none"}
- **Failing tests/checks:** {any known failures, or "all passing"}
- **Build status:** {compiles/broken/unknown}

## Next steps
1. {highest priority next action}
2. {second priority}
3. {etc.}

## Blockers / Open questions
- {anything unresolved that needs attention}

## Key context
- {non-obvious decisions made this session}
- {gotchas or traps the next session should know about}
- {relevant issue numbers}
```

### Step 3: Confirm with user

Show the handoff contents and ask if they want to add or change anything before saving.

## Guidelines

- Be specific — "updated service.py" is useless; "renamed query_revision → query_chapter_content in novels/service.py, 4 callers updated" is useful.
- Include file paths and function names where relevant.
- If there are known test failures, list them explicitly.
- Reference GitHub issue numbers where applicable.
- Keep it under 50 lines — this is a quick-start guide, not documentation.
