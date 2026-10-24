---
name: kata
version: 0.1.0
mission: A gate before a part the script doesn't have.
parts:
  coder:
    writes: [app/]
gates:
  - { name: plan, before: [builder] }
---

The **coder** builds after **Gate: plan**.
