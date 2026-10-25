---
name: triage-a-failure
description: How to turn a failing check after the build into one fix task for one workstream. Load when tests fail after the build.
---

# Triage a failure

1. Read the failure: which tests fail, and what they say.
2. Find the workstream whose paths hold the code those tests exercise. A failure can need more than one fix; write
   one task per workstream.
3. Add a section to `tasks/round-<n>.md` for each fix: `fix: <workstream>`, its paths (unchanged), the failing tests,
   and what the failure suggests is wrong. Never suggest changing a test.
