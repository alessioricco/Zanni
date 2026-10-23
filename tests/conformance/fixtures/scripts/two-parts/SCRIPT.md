---
name: two-parts
version: 1.0.0
mission: A fixture script with two parts.
parts:
  writer:
    seats: 1-3
  reviewer:
    optional: true
gates: [publish]
---

The **writer** writes; the **reviewer** reviews.
