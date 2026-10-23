---
name: write-test
description: How to write one test for one acceptance criterion. Load before writing any test from the backlog.
---

# Write a test

1. Find the criterion's exact input and expected output in `backlog/`.
2. Write one test named after the criterion, with a single assertion comparing actual and expected.
3. Save it under `tests/`, next to the tests for the same feature.
4. Run it and confirm it fails for the right reason before reporting.
