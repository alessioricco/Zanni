---
name: check-files
version: 1.0.0
mission: A fixture script whose verifier runs a check file shipped in its package (D55).
parts:
  tester:
    writes: [tests/]
verifiers:
  tests-cover-criteria:
    description: every criterion in the backlog has a test that names its id
    command: [python3, "${ZANNI_SCRIPT}/checks/criteria.py", backlog, tests]
    files: [checks/criteria.py]
---

The **tester** writes a test per criterion. *Verifier:* `tests-cover-criteria`.
