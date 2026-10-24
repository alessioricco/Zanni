---
name: with-verifiers
version: 1.0.0
mission: A fixture script with verifiers, one of them without a default command.
parts:
  coder:
    seats: 1-2
    writes: [app/]
verifiers:
  tests-pass:
    description: the project's tests pass
    command: [pytest, -q]
  lint:
    description: the code passes the project's linter
stop:
  max_rounds: 2
  done_when: [tests-pass]
---

The **coder** makes the tests pass. *Verifier:* `lint`, then `tests-pass`.
