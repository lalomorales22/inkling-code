---
name: test
description: Write meaningful tests for existing code, verified failing-first
---
Add real tests for the target code — tests that would catch an actual regression.

1. Read the code under test completely, and find how existing tests in this
   repo are structured (framework, file naming, fixtures, how they run).
   Match those conventions exactly.
2. List the behaviours worth pinning: the happy path, each documented edge
   (empty, zero, None, unicode, boundaries), and each error path that callers
   depend on. Skip trivial getters and framework plumbing.
3. For every test, prove it can fail: write it, mentally (or actually) break
   the code, and confirm the test would catch it. A test that passes against
   broken code is decoration.
4. No mocking what you can use directly; mock only true externals (network,
   clock, filesystem where impractical). Over-mocked tests pin implementation,
   not behaviour.
5. Run the suite. Every new test green, every old test still green. Report the
   coverage you added and anything you found untestable (that's a design
   smell worth mentioning).
