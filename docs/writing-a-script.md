# Writing a script

A script is the reusable work: what must be achieved, which parts are needed, the workspace it expects, and how the work unfolds. You write it once, and any number of plays can perform it with their own actors, director and stage, the way one theatre script is staged by many companies.

> **Status:** `zanni` validates scripts, and runs them: `zanni play.yaml` starts a director that follows a play's script (milestone 4).

## The shape

A script is a Markdown file named `SCRIPT.md`, in its own folder if it has other files. It has two parts:

- **Frontmatter:** between `---` lines at the top, it holds only what must be checked.
- **Prose:** everything else, written for the director, an agent that reads it and gives the actors their cues.

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
The **editor** splits `brief.md` into angles and assigns one to each **reporter**.
Each reporter writes `drafts/<angle>.md` and saves every source it cites in `sources/`.

## Act 2: Check
The **fact-checker** checks each claim in the drafts against its cited source …
*Verifier:* every link in `sources/` resolves, and every claim has a check.

## Act 3: Edit
The **editor** merges the drafts into `final/article.md`, dropping unsupported claims.
**Gate: publish.** A human approves before anything is published.
```

Three complete examples are in the repository: `examples/scripts/slug-kata/` (small, and runnable: [getting started](getting-started.md#running-a-play)), `examples/scripts/software-team/` and `examples/scripts/newsroom/`.

## 1. Name the parts

`parts` lists who the work needs, with no names of real roles or actors. For each part you can set:

- **`seats`:** how many actors may hold it, such as `1-3`. A play can narrow the range but not widen it.
- **`writes` and `reads`:** the most this part may touch on the stage. They are ceilings: a seat gets what its role asks for, within them, and the stage enforces it. Leave them out to set no ceiling.
- **`suggested`:** a role a play may cast, such as `github.com/zanni-roles/editor@0.1.0`. A play may cast another.
- **`optional: true`:** a play may leave this part uncast.
- **`description`:** a sentence for whoever casts the part.

## 2. Say what the workspace must hold

`stage.expects` lists what must be on the stage before the play starts, such as `vision.md` or `brief.md`. The script never says what kind of stage it is: a play picks a git repository or a folder.

## 3. Mark the gates, the verifiers and the stop rules

- **`gates`:** names the moments a human must approve, such as `plan`, `release` or `publish`. Mark each one in the prose where it happens. A play may enforce any of them, and no others.
- **`verifiers`:** the checks the director runs on the stage, by name, each with a `description` and, usually, a default `command`. A verifier passes when its command exits 0, run in the stage folder. A play gives its own command when its project needs another, such as `npm test` instead of `pytest`.

  ```yaml
  verifiers:
    tests-fail:
      description: the tests run, and at least one fails (new tests fail before the code exists)
      command: [uv, run, --no-project, --with, pytest, python, -c, "import subprocess, sys; sys.exit(0 if subprocess.call([sys.executable, '-m', 'pytest', '-q', 'tests']) == 1 else 1)"]
    tests-pass:
      description: every test passes
      command: [uv, run, --no-project, --with, pytest, python, -m, pytest, -q, tests]
  ```

- **`stop`:** sets hard limits for repeating work, such as `max_rounds: 5` and `budget_per_round: 2.00`, and what "done" means: `done_when` names the verifiers that must pass, on the stage as it is when the director stops, such as `done_when: [tests-pass]`. Without it, "done" only needs one verifier passed in the last round, and the log says it was weakly checked. The play's own budget applies on top.

Not every verifier has to pass at the end: "the new tests fail" is a check for one scene, and fails once the code exists. Only `done_when` says what "done" means.

## 4. Write the prose for the director

The director is an agent and follows the prose. It never acts on it directly: it acts through a few tools (`cue`, `wait_for_reports`, `run_verifier`, `ask_gate`, `cast`, `release`, `end_round`, `stop`), and each tool checks the frontmatter's rules in code before acting. So the prose decides the order of the work, and the frontmatter decides what is allowed (D33). Write for it like this:

- **Acts and scenes:** organise the work into acts and scenes in Markdown headings.
- **Parts:** name the parts in **bold** where they act, so the director knows whom to cue.
- **Paths:** say which stage paths each scene reads and writes.
- **Verifiers:** refer to them by their name in `verifiers` where a check decides whether the work is done (*Verifier:* `tests-pass`). Work is done when a verifier says so, not when an actor does.
- **Actors never see the script:** the director writes each cue for one actor. Say what each part needs to know (the files, the module, the backlog item), so the director can pass it on.
- **Repetition:** say when to repeat and when to stop, in plain words, and back it with `stop` in the frontmatter.

Keep it generic: the script must work with any roles a play casts, on any stage backend.

## 5. Check it

```bash
uv run zanni examples/scripts/newsroom             # a folder holding SCRIPT.md
uv run zanni examples/scripts/newsroom/SCRIPT.md   # or the file
```

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

Then check a play against it. When a play's `script:` is a local path, `zanni --check play.yaml` checks that the play:

- casts the script's parts;
- keeps seats within the script's limits;
- uses only the script's gates;
- gives a command for every verifier the script has none for, and none for verifiers it doesn't have.

It then lists every verifier command the director would run, and whether it came from the script or the play: they run with your permissions.

## 6. Publish it

Publish a script like a role: in a git repository, tagged `vX.Y.Z` (or `path/to/script/vX.Y.Z` for one in a subfolder). Plays then refer to it as `github.com/you/newsroom@0.1.0`; the director fetches it with git, and pins it in the play's `play.lock` (D37).

Every field is in the [script spec](spec/script.md).
