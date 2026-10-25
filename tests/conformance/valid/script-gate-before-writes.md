---
name: gate-before-writes
version: 1.0.0
mission: A fixture script whose plan gate holds back paths, not parts (D62).
parts:
  architect:
    writes: [spec/, reviews/]
gates:
  - { name: plan, every: round, before_writes: [spec/] }
---

The **architect** reviews the backlog in `reviews/`, then, after the **plan** gate, writes `spec/`.
