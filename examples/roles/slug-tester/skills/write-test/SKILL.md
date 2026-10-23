---
name: write-test
description: How to write one pytest test for one acceptance criterion. Load before writing any test.
---

# Write a test

1. Find the criterion's exact input and expected output in the backlog.
2. Import the code under test the way the cue or the spec names it.
3. Write one function `test_<criterion_id>` with a single `assert` comparing actual and expected.
4. Write the whole test file in one `stage_write` call. Don't create `__init__.py`, fixtures or helpers.
