---
name: kata
version: 0.1.0
mission: Make the tests pass, checked by verifiers.
parts:
  coder:
    writes: [app/]
verifiers:
  tests-fail:
    description: every new test fails
    command: [pytest, -q, --co]
    timeout: 60
  tests-pass:
    description: every test passes
    command: [pytest, -q]
stop:
  max_rounds: 2
  done_when: [tests-pass]
---

The **coder** makes the tests pass. *Verifier:* `tests-pass`.
