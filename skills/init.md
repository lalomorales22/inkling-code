---
name: init
description: Study this project and generate a solid INKLING.md
---
Create an INKLING.md so future sessions start already knowing this project.

1. Explore before writing: list the tree (ignoring node_modules/.venv/build
   artifacts), read the manifest (pyproject/package.json/Cargo.toml/go.mod),
   the README, CI config, and skim the entry points.
2. Establish, from evidence: what the project does, how to run it, how to test
   it, how to lint/format it, the layout of important directories, and any
   conventions the code visibly follows (naming, error handling, imports).
3. Write INKLING.md in the project root — short and dense, for an agent, not
   marketing. Sections: What this is · Commands (run/test/lint as exact shell
   lines) · Layout (only load-bearing paths) · Conventions (only real,
   observed ones).
4. Keep it under ~60 lines. Every line must be verifiable from the repo; if you
   didn't see it, don't write it. If an INKLING.md already exists, update it
   rather than replacing it wholesale.
5. Show the result.
