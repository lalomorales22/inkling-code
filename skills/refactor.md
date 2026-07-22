---
name: refactor
description: Restructure code safely behind a green test suite
---
Refactor the target code without changing behaviour.

1. Establish the safety net first: run the test suite and record what passes.
   If the code you're about to touch has no tests, write a characterization
   test for its current behaviour before moving anything.
2. Map every caller of what you're changing (`search` for the symbol) — the
   refactor isn't scoped until you know its blast radius.
3. Move in small mechanical steps, re-running tests after each: rename, then
   extract, then relocate — never all at once. Keep each step compiling.
4. Preserve public interfaces unless the user asked to change them; if a
   signature must change, update every call site in the same pass.
5. Resist scope creep: no drive-by behaviour "fixes", no reformatting files you
   didn't otherwise touch. Note anything broken you find, and leave it.
6. Finish with the full suite green and a summary of what moved where and why
   it's now better.
