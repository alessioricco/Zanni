---
name: gate-before-writes-empty
version: 1.0.0
mission: A gate holding back an empty path.
parts:
  architect:
    writes: [spec/]
gates:
  - name: plan
    before_writes: [""]
---

The **architect** writes the spec after the **plan** gate.
