---
name: answer-reviews
description: How to revise the architecture once after its reviews. Load when reviews of the spec are in reviews/round-<n>/.
---

# Answer reviews

1. Read every review in `reviews/round-<n>/` that is about the spec: `spec-<part>.md`.
2. For each point, decide: change the design, or keep it and say why. You decide; reviewers advise.
3. Rewrite the files under `spec/architecture/` once, with the changes.
4. Write `reviews/round-<n>/spec-answers.md`: one line per review point, what you did about it, and why.
