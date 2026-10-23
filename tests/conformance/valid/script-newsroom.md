---
name: newsroom
version: 0.1.0
mission: Turn a brief into a published article whose every claim is checked against a cited source.
parts:
  editor:
    writes: [brief.md, final/]
  reporter:
    seats: 1-3
    writes: [drafts/, sources/]
  fact-checker:
    reads: [drafts/, sources/]
    writes: [checks/]
stage:
  expects: [brief.md]
gates: [publish]
---

# Newsroom

## Act 1: Report
The **editor** splits `brief.md` into angles and assigns one to each **reporter**.
Each reporter writes `drafts/<angle>.md` and saves every source it cites in `sources/`.

## Act 2: Check
The **fact-checker** checks each claim in the drafts against its cited source,
and writes `checks/<angle>.md`, marking each claim as supported or not.
*Verifier:* every link in `sources/` resolves, and every claim has a check.

## Act 3: Edit
The **editor** merges the drafts into `final/article.md`, dropping unsupported claims.
**Gate: publish.** A human approves before anything is published.
