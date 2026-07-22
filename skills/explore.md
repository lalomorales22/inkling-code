---
name: explore
description: Map an unfamiliar codebase into a working mental model
---
Build a fast, accurate map of this codebase and report it.

1. Skeleton first: directory tree (2 levels, ignoring dependencies/build dirs),
   manifest, README, entry points. Identify the language, framework, and how
   the thing is started and tested.
2. Follow one real path end to end — a request, a command, a data record —
   reading the actual files, not just their names. This one traced path teaches
   more than listing every module.
3. Note as you go: where state lives, where side effects happen, what the
   central types/tables are, and which modules everything else imports
   (those are the load-bearing walls).
4. Use the task tool for breadth (e.g. "find every place X is handled") so the
   details stay out of your main context.
5. Report as: what it is · how it runs · the 5–8 files that matter most and
   why · the one path you traced, step by step · anything surprising.
   Concrete paths everywhere; no generic architecture prose.
