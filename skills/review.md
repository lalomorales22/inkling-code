---
name: review
description: Code-review the current diff for real bugs, not style noise
---
Review the pending changes in this repository like a careful senior engineer.

1. `git status` and `git diff HEAD` (or `git diff main...HEAD` on a branch) to
   collect the change set. Read every touched file around the changed lines —
   a diff hunk without its surroundings lies.
2. Hunt in priority order:
   - **Correctness**: logic errors, inverted conditions, off-by-ones, unhandled
     None/empty/error paths, broken invariants callers rely on.
   - **Integration**: does every caller of a changed signature still work?
     Search for usages rather than assuming.
   - **Security**: injection via string-built commands/SQL/HTML, secrets in
     code, unvalidated external input reaching something dangerous.
   - **Silent failure**: swallowed exceptions, ignored return codes.
3. For each finding, verify it before reporting: construct the concrete input
   or state that triggers it. Drop anything you cannot make fail in your head.
4. Report findings ranked by severity, each as: file:line — what breaks, and the
   scenario that breaks it. If the diff is clean, say it is clean; do not invent
   nitpicks to look useful. Style comments only when they hide a defect.

Do not change any files unless the user asks you to fix what you found.
