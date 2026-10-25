---
name: write-backlog
description: How to write a round's backlog, with acceptance criteria that tests can name. Load before writing backlog/round-<n>.md.
---

# Write a backlog

1. Pick three to six items for this round: what the vision needs next, and the open findings worth fixing now.
2. Give each item a short title and one sentence on why it matters to the person using the app.
3. Under each item, list its acceptance criteria. Each criterion gets an id, `R<round>-<number>`, numbered across
   the whole round: `R1-1`, `R1-2`, … Testers name these ids in their tests, and a verifier checks every one has a
   test.
4. Write each criterion as something a test can check: an input, an action and the result someone could observe.
   "Converting 1 km gives 1000 m" can be tested; "conversion is easy" can't.
5. Say what is out of scope for the round, in one line, so nobody builds it.

```markdown
# Round 1

## Convert lengths
Someone can turn a length in one unit into another.
- R1-1: converting 1 km to m gives 1000
- R1-2: converting 12 in to cm gives 30.48

Out of scope: currencies.
```
