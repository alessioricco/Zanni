---
name: check-file-missing
version: 1.0.0
mission: A verifier lists a check file the package doesn't have.
parts:
  tester:
    writes: [tests/]
verifiers:
  tests-cover-criteria:
    description: every criterion has a test
    command: [python3, "${ZANNI_SCRIPT}/checks/criteria.py"]
    files: [checks/criteria.py]
---

The **tester** writes tests.
