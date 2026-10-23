---
name: software-team
version: 1.0.0
mission: Turn vision.md into a working app, in rounds, with every change checked by verifiers.
parts:
  product-owner:
    description: Decides what to build and in what order.
    suggested: github.com/zanni-roles/product-owner@1.0.0
    writes: [backlog/]
  architect:
    writes: [spec/architecture/]
  ui-designer:
    writes: [spec/ui/]
    optional: true
  tester:
    writes: [tests/, findings/]
  developer-lead:
    writes: [tasks/]
  coder:
    seats: 1-8
    writes: [app/]
stage:
  expects: [vision.md]
gates: [plan, release]
stop:
  max_rounds: 5
---

# Software team

## Act 1: a round (repeat until a stop rule)

### Scene 1: Plan
The **product owner** reads `vision.md` and `findings/`, picks this round's items,
and writes `backlog/round-<n>.md` with acceptance criteria for each.
**Gate: plan.** A human approves the plan before anything else happens.

### Scene 2: Specify
The **architect** and the **UI designer** write the spec for these items.
The **tester** writes a failing test for every acceptance criterion.
*Verifier:* every criterion has a test, and every new test fails.

### Scene 3: Build
The **developer lead** groups the items into workstreams in `tasks/`.
The director casts one **coder** per workstream; each changes only its workstream's paths.
*Verifier:* the project's tests pass on each workstream.

### Scene 4: Merge and check
The **developer lead** merges the workstreams.
*Verifier:* the full test suite and the browser tests pass on the merged app.

### Scene 5: Explore
The **tester** explores the running app; each bug becomes a failing test and a finding.

### Scene 6: Review
The **product owner** reviews against `vision.md`. Stop if this round added no verified items.
**Gate: release.**
