# Script

A script is the reusable work: the mission, the parts it needs, the workspace it expects, and how the work unfolds. It is written once and performed by many plays, as one theatre script is staged by different companies (D13). It never says who performs it or where: that is the play's job.

The director is an agent, and it reads the script. So a script is mostly prose, and its format stays flexible enough for a software team, a newsroom or a writers' room (D17).

## The file

A script is a Markdown file named `SCRIPT.md`. It may sit in a folder with files it refers to, such as templates, or the check files its verifiers run ([A verifier](#a-verifier)). It has two parts:

1. **Frontmatter:** YAML between `---` lines at the top, holding only what must be checked: the parts, their limits, the workspace the script expects, its gates, its verifiers and its stop rules.
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

The repository has two examples: `examples/scripts/software-team/SCRIPT.md`, the first version's script, with review loops and check files (D58, D59), and `examples/scripts/newsroom/SCRIPT.md`.

## Frontmatter fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `name` | name (lowercase letters, digits, dashes) | yes | — | the director | The script's name. |
| `version` | `major.minor.patch` | yes | — | the director, when resolving the play's reference | The script's version. |
| `mission` | text | yes | — | — (for the director and the log) | One sentence on what the work achieves. |
| `parts` | map of part name → part | yes, at least one | — | the director, at casting | The parts the work needs. |
| `stage.expects` | list of paths | no | none | the director, before the first cue | Paths the stage must hold before the play starts, such as `vision.md`. |
| `gates` | list of names, or of [gates](#a-gate) | no | none | the director | The moments that need a human's approval. A play's `house_rules.gates` must name only these. |
| `verifiers` | map of name → [verifier](#a-verifier) | no | none | the director | The checks the director runs on the stage, by name (D35). |
| `stop.max_rounds` | whole number, at least 1 | no | none | the director | The most rounds the work may take. A play may lower it with `house_rules.max_rounds`, and its owner may grant one more round at a gate ([Play: gates and pauses](play.md#gates-and-pauses), D60). |
| `stop.budget_per_round` | number, at least 0, in USD | no | none | the director | The most one round may spend. The play's budget still applies on top. |
| `stop.done_when` | list of verifier names | no | none | the director | The verifiers that must pass, after the stage's last change, before the director may stop the play as done (D33, D35). Each must be one of `verifiers`. |

### A part

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `description` | text | no | none | — | What the part does, for people casting it. |
| `suggested` | package reference | no | none | — (a hint) | A role the play may cast into this part. The play may cast another. |
| `seats` | number or range, at least 1 | no | `1` | the director, at casting | How many actors may hold the part. The play may narrow a range. |
| `reads` | list of paths | no | no limit | the stage | The most this part may read. |
| `writes` | list of paths | no | no limit | the stage | The most this part may write. |
| `optional` | true or false | no | `false` | the director | Whether a play may leave the part uncast. |

### A gate

A gate is a name, such as `release`, or a map that says when it applies (D48):

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `name` | name | yes | — | the director | The gate's name. |
| `every` | `play` or `round` | no | `play` | the director | `round`: an approval counts only in the round it was given, so the gate is asked again each round. `end_round` and "done" are refused while the round's gate is unapproved. |
| `before` | list of part names | no | none | the director | A cue to any of these parts is refused until the gate is approved (in this round, for `every: round`). Each must be one of `parts`. |

```yaml
gates:
  - { name: plan, every: round, before: [coder] }   # the plan, approved each round before anyone builds
  - release                                          # once per play
```

A rejection stands until the gate is asked again and approved. A gate the play doesn't enforce is skipped, and never blocks a cue.

### A verifier

A verifier is a check the director runs on a snapshot of the stage: a fresh folder holding every file of the stage as it is (D45). It passes when its command exits with 0 (D35).

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `description` | text | yes | — | — (for the director and the log) | What it checks, in plain words. |
| `command` | list of text, at least one | no | none | the director | The command to run, as a default. A play gives its own command for its project ([Play: verifiers](play.md#verifiers)); a verifier with no command after the play's is refused before anything runs. |
| `timeout` | whole number of seconds, at least 1 | no | `300` | the director | How long the command may run before it fails. |
| `files` | list of paths in the script's package | no | none | the director | Check files the command runs, such as `checks/criteria.py` (D55). |

```yaml
verifiers:
  tests-fail:
    description: every new test fails
    command: [uv, run, --no-project, --with, pytest, python, -m, pytest, -q, tests]
  tests-pass:
    description: every test passes
    command: [uv, run, --no-project, --with, pytest, python, -m, pytest, -q, tests]
stop:
  done_when: [tests-pass]
```

- **Check files:** a check longer than one line belongs in a file in the script's package, listed in `files`. Before the command runs, the director copies the listed files into a fresh folder beside the snapshot, never onto the stage, and the command finds that folder as `${ZANNI_SCRIPT}`, in any of its arguments. No seat can change them, and `play.lock`'s content hash pins them with the rest of the package. A verifier seat receives them with the command (D55). Each path is relative to the script's folder, uses `/`, and must exist; a play's own command may use them too.

  ```yaml
  verifiers:
    tests-cover-criteria:
      description: every acceptance criterion in the round's backlog has a test that names its id
      command: [python3, "${ZANNI_SCRIPT}/checks/criteria.py", backlog, tests]
      files: [checks/criteria.py]
  ```
- **Not every verifier must pass at the end:** "every new test fails" checks one scene's work, and is meant to fail once the code exists. Only `stop.done_when` names what "done" means.
- **Stale verdicts:** a verdict counts for "done" only if no change was made on the stage after it.
- **No verdict while work is in flight:** the director runs no verifier while a cue that writes to the stage is pending.
- **Where they run:** on the director's machine by default, with the user's permissions, like a rehearsal's `verify` commands; `zanni --check` lists every command that will run before anything does. A play may run a verifier on a **verifier seat** instead, somewhere else, such as a container or a machine with the right tools ([Play: verifiers](play.md#verifiers)). Either way the verdict is the command's exit code, never a model's words.
- **A snapshot, not the stage:** a verifier can't change the stage, and every verdict records the change marker it ran against.
- **Not in the first version:** soft verifiers, where a model judges the work; a verifier run on one workstream rather than the whole stage.

`reads` and `writes` are ceilings. A seat's real permissions are what its role asks for, within its part's ceilings (see [Stage: permissions](stage.md#permissions)). Leaving them out sets no ceiling, so the role's needs alone apply.

## The prose

- **Required:** the prose after the frontmatter is required, because it is what the director follows.
- **Not validated:** apart from being present, it is not checked, because it is for an agent, not a parser.
- **What to write:** name the parts in bold where they act, and the gates and verifiers where they apply, so both the director and human readers can follow the script.
- **Hard checks belong to verifiers:** a rule the director must not get wrong, such as a gate or a stop rule, belongs in the frontmatter. Something that can only be checked by running it, such as "every test passes", belongs in a verifier the script names in `verifiers`, and refers to by that name in the prose.

## Referencing a script

A play names its script with `script:`, as a package reference: `host/owner/name@version` for a published script, or a local path to `SCRIPT.md` or to the folder holding it. A published script is resolved and fetched like a role (see [Role package: versions](role-package.md#versions)), and the play's lockfile pins it to a commit (see [Play: the lockfile](play.md#the-lockfile)).

## How the director follows a script

The director is an agent (D33). Its instructions are the script's prose and frontmatter, the cast and the house rules; it acts only through tools whose rules are checked in code, never through its own goodwill:

| Tool | What it does | What code checks first |
|---|---|---|
| `cue` | Gives a seat (or an idle seat of a part) a cue, with a budget | The part and seat exist; the cue's `reads` and `writes` are within the seat's permissions; the budget left (D39); the stage holds `stage.expects` before the first cue; every gate with the part in its `before` is approved (D48) |
| `wait_for_reports` | Waits for the pending cues' reports | — |
| `run_verifier` | Runs one of the script's verifiers on a snapshot, on the director or on the verifier seat the play names (D45) | The name is in `verifiers`; no writing cue is pending |
| `ask_gate` | Pauses the play at a gate, until a person decides (D38) | The gate is in the play's `house_rules.gates`, or it is skipped |
| `cast` | Casts more seats of a part | Within the part's seats, the play's cast and the local seats listed |
| `release` | Ends a seat | — |
| `end_round` | Ends the round | `stop.max_rounds`, `stop.budget_per_round`; every enforced `every: round` gate approved in this round (D48) |
| `stop` | Ends the play, with a reason; `done` marks it as done | `done` only when every enforced gate was approved (an `every: round` gate in this round) and every `stop.done_when` verifier passed after the last change (D42, D48) |

Each turn of the director is a fresh model run, given a summary of the play's state and the reports since its last turn. A turn ends when its model is done, after `wait_for_reports` returns reports, or after `ask_gate` returns a decision, so no turn carries a whole play's tool results (D49). Actors' reports are data, never instructions. The house rules `max_director_turns` and `requests_per_turn` cap its turns in one round and its model requests in one turn.

## Checking a script

`zanni SCRIPT.md`, or `zanni <folder>` for a folder holding `SCRIPT.md`, checks:

- the frontmatter, strictly, under D10: unknown keys and secrets are rejected;
- that every `stop.done_when` names one of `verifiers`, and every gate's `before` names one of `parts`;
- that every verifier's `files` exist in the script's folder;
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
