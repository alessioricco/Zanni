---
name: make-the-tests-pass
description: How to make one workstream's failing tests pass, in the project's own stack. Load before writing code.
---

# Make the tests pass

1. Read your workstream in `tasks/`: its paths, its criteria and its tests. Then the contracts it implements in
   `spec/architecture/`, and the tests themselves.
2. Run the test command from the spec in your workspace, and read what fails.
3. Write the simplest code, in the project's stack, that makes those tests pass, keeping the contracts' names and
   signatures. Write only inside your workstream's paths.
4. Run the tests again. Repeat until your workstream's tests pass. Tests of other workstreams may still fail; they
   aren't yours.
5. Never edit a test, and never add a dependency the project's files don't list.
