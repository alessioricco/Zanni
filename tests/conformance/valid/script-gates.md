---
name: kata
version: 0.1.0
mission: Make the tests pass, with the plan approved every round before anyone builds.
parts:
  tester:
    writes: [tests/]
  coder:
    writes: [app/]
gates:
  - { name: plan, every: round, before: [coder] }
  - release
---

The **tester** writes the round's tests. **Gate: plan**, every round, before the **coder** builds. **Gate: release**, once.
