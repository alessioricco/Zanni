---
name: check-file-outside
version: 1.0.0
mission: A verifier lists a check file outside its package.
parts:
  tester:
    writes: [tests/]
verifiers:
  tests-cover-criteria:
    description: every criterion has a test
    command: [python3, "${ZANNI_SCRIPT}/criteria.py"]
    files: [../criteria.py]
---

The **tester** writes tests.
