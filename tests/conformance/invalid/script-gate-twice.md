---
name: kata
version: 0.1.0
mission: The same gate listed twice.
parts:
  coder:
    writes: [app/]
gates:
  - plan
  - { name: plan, every: round }
---

The **coder** builds after **Gate: plan**.
