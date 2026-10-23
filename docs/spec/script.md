# Script

A script is the reusable work: the mission, the parts it needs, the workspace it expects, and how the work unfolds. It is written once and performed by many plays, as one theatre script is staged by different companies (D13). It never says who performs it or where: that is the play's job.

The director is an agent, and it reads the script. So a script is mostly prose, and its format stays flexible enough for a software team, a newsroom or a writers' room (D17).

## The file

A script is a Markdown file named `SCRIPT.md`. It may sit in a folder with files it refers to, such as templates. It has two parts:

1. **Frontmatter:** YAML between `---` lines at the top, holding only what must be checked: the parts, their limits, the workspace the script expects, its gates and its stop rules.
2. **Prose:** everything else, for the director: acts, scenes, cues, hand-offs and verifiers.

```markdown
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
The **editor** splits `brief.md` into angles and assigns one to each **reporter**. …
```

The repository has two examples: `examples/scripts/software-team/SCRIPT.md`, the first version's script, and `examples/scripts/newsroom/SCRIPT.md`.

## Frontmatter fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `name` | name (lowercase letters, digits, dashes) | yes | — | the director | The script's name. |
| `version` | `major.minor.patch` | yes | — | the director, when resolving the play's reference | The script's version. |
| `mission` | text | yes | — | — (for the director and the log) | One sentence on what the work achieves. |
| `parts` | map of part name → part | yes, at least one | — | the director, at casting | The parts the work needs. |
| `stage.expects` | list of paths | no | none | the director, before the first cue | Paths the stage must hold before the play starts, such as `vision.md`. |
| `gates` | list of names | no | none | the director | The moments that need a human's approval. A play's `house_rules.gates` must name only these. |
| `stop.max_rounds` | whole number, at least 1 | no | none | the director | The most rounds the work may take. |
| `stop.budget_per_round` | number, at least 0, in USD | no | none | the director | The most one round may spend. The play's budget still applies on top. |

### A part

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `description` | text | no | none | — | What the part does, for people casting it. |
| `suggested` | package reference | no | none | — (a hint) | A role the play may cast into this part. The play may cast another. |
| `seats` | number or range, at least 1 | no | `1` | the director, at casting | How many actors may hold the part. The play may narrow a range. |
| `reads` | list of paths | no | no limit | the stage | The most this part may read. |
| `writes` | list of paths | no | no limit | the stage | The most this part may write. |
| `optional` | true or false | no | `false` | the director | Whether a play may leave the part uncast. |

`reads` and `writes` are ceilings. A seat's real permissions are what its role asks for, within its part's ceilings (see [Stage: permissions](stage.md#permissions)). Leaving them out sets no ceiling, so the role's needs alone apply.

## The prose

- **Required:** the prose after the frontmatter is required, because it is what the director follows.
- **Not validated:** apart from being present, it is not checked, because it is for an agent, not a parser.
- **What to write:** name the parts in bold where they act, and the gates and verifiers where they apply, so both the director and human readers can follow the script.
- **Hard checks belong to verifiers:** a rule the director must not get wrong, such as a gate or a stop rule, belongs in the frontmatter. Something that can only be checked by running it, such as "every test passes", belongs in a verifier the script names.

## Referencing a script

A play names its script with `script:`, as a package reference: `host/owner/name@version` for a published script, or a local path to `SCRIPT.md` or to the folder holding it. A published script is resolved like a role (see [Role package: versions](role-package.md#versions)), and the play's lockfile pins it to a commit (see [Play: the lockfile](play.md#the-lockfile)).

## Checking a script

`zanni SCRIPT.md`, or `zanni <folder>` for a folder holding `SCRIPT.md`, checks:

- the frontmatter, strictly, under D10: unknown keys and secrets are rejected;
- that the prose is present.

```
Script: 'newsroom' 0.1.0.
  mission: Turn a brief into a published article whose every claim is checked against a cited source.
  parts:
    editor: 1 seat; writes brief.md, final/
    reporter: 1-3 seats; writes drafts/, sources/
    fact-checker: 1 seat; writes checks/
  gates: publish
  stop rules: none in the frontmatter
Valid.
```
