---
name: commit
description: Review staged/unstaged changes and write a clean, factual commit
---
Create a well-formed git commit from the current working tree.

1. Run `git status` and `git diff HEAD` to see everything that changed. Also
   `git log --oneline -8` to match the repo's existing message style.
2. Decide what belongs in this commit. If the diff contains unrelated changes,
   say so and commit only the coherent set (use `git add <paths>`, not `git add -A`,
   when the tree is mixed).
3. Write the message from the diff, not from memory:
   - Subject ≤ 72 chars, imperative mood ("Add", "Fix", "Rename"), no trailing period.
   - Explain *why* in the body only when the diff doesn't make it obvious.
   - Never invent ticket numbers, co-authors, or scope tags the repo doesn't use.
4. Commit. If a pre-commit hook rewrites files, re-stage and amend once.
5. Show `git log -1 --stat` as confirmation.

Do not push unless explicitly asked. Never use `--force`, `--no-verify`, or amend
commits that are already pushed.
