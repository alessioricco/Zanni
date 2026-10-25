---
name: write-ui-spec
description: How to describe a screen so it can be tested and built. Load before writing spec/ui/.
---

# Write a UI spec

1. One file per screen or flow: `spec/ui/<screen>.md`.
2. For each screen: its address (such as `/`), its purpose in one line, and which criteria it serves, by id.
3. List its elements in order: each one's label, kind, and any stable name a test can find it by, such as an `id`.
4. Describe each action: what the person does, and what they see after. Include what they see on a wrong input.
5. Keep to what the round's items need. No colours or fonts unless the vision asks for them.
