---
name: one-test-per-criterion
description: How to write one failing test for each acceptance criterion, named by its id. Load before writing tests.
---

# One test per criterion

1. Read the round's backlog and every criterion id in it, such as `R1-3`, and the spec's contracts and commands.
2. Write one test for each criterion, in the project's test runner, in the test folder the spec names under `tests/`.
3. Name the criterion's id in the test: in its name, as `r1_3` (a function name can't hold a dash), or in its
   description, as `R1-3`. A verifier checks that every id has a test.
4. Test the behaviour the criterion describes, through the contract the spec gives, not the code's insides.
5. Run the tests in your workspace with the spec's test command. Before the code exists they must fail, and fail
   because the behaviour is missing, not because a test is broken. Fix a broken test; never make one pass.
