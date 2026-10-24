---
name: kata
version: 0.1.0
mission: m
parts:
  coder: {}
verifiers:
  tests-pass: { description: every test passes, command: [pytest] }
stop:
  done_when: [tests-pass, all-green]
---

Prose.
