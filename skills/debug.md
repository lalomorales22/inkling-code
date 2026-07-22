---
name: debug
description: Reproduce, isolate and fix a bug — evidence over guessing
---
Debug the reported problem systematically. The rule: never change code you
haven't first proven is the cause.

1. **Reproduce.** Run the failing thing exactly as described. If you can't
   reproduce it, say so and gather more detail — don't fix blind.
2. **Read the error.** The actual message, the actual stack, the actual line.
   Follow it to real code and read the surrounding function whole.
3. **Localize.** Bisect the path from input to failure: add a temporary print
   or assertion at the midpoint, run, and halve again. Prefer evidence from
   running code over theories from reading it.
4. **Understand before fixing.** State (to yourself) the one-sentence cause:
   "X is None here because Y skips initialization when Z." If you can't say
   that sentence yet, keep localizing.
5. **Fix the cause, not the symptom.** No blanket try/except, no `if x is None:
   return` bandaids over broken invariants.
6. **Verify.** Re-run the original reproduction and the wider test suite.
   Remove any temporary instrumentation you added.
7. Report: cause, fix, and proof it's fixed, in three sentences.
