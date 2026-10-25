---
name: plan-workstreams
description: How to split a round into workstreams whose paths don't overlap. Load before writing tasks/round-<n>.md.
---

# Plan workstreams

1. Read the round's backlog, the spec's modules and contracts, and the tests.
2. Group the work into as few workstreams as the round needs; one is fine. Each workstream gets:
   - **paths:** the files or folders under `app/` it may write, as a list. No path may appear in two workstreams,
     and no path may sit inside another workstream's folder.
   - **criteria:** the ids it makes pass, such as `R1-1, R1-2`, and the tests that check them.
   - **depends on:** another workstream whose contract it uses, if any; the contract is in the spec, so it can be
     built at the same time.
3. A file several workstreams need, such as an entry point, belongs to exactly one of them. The others use it
   through its contract.
4. Write `tasks/round-<n>.md`, one section per workstream, starting with its name and its paths:

```markdown
## convert
paths: [app/convert.py]
criteria: R1-1, R1-2 (tests/test_convert.py)
```
