# Zanni files

There is one command, `zanni <file>`, and three kinds of file. The kind comes from the file's keys, never from its name or a flag:

| Kind | Recognised by | What `zanni` would run | Full field list |
|---|---|---|---|
| Actor file | `role` and `play` | an actor that joins the play | [spec: actor file](spec/actor-file.md) |
| Play file | `cast` | the play's director | [spec: play folder](spec/play-folder.md) |
| Role manifest (`role.yaml`) | `mission` | nothing; it is validated | [spec: role package](spec/role-package.md) |

## Rules for every file

- **Unknown keys are errors.** A typo gets a "did you mean": a misspelled limit must never become a silent default.
- **Duplicate keys are errors.** Plain YAML would silently keep the last one.
- **No secrets.** A key that looks like a secret (`api_key`, `token`, `password`, `client_secret`, …) is rejected at any depth. Secrets go in the environment or a git-ignored `.env`; see [Models and keys](models-and-keys.md).
- **Defaults everywhere.** A file only says what differs from the defaults. The spec pages list every field with its default.
- **Every problem at once.** `zanni` reports all the problems in a file in one go, each with its line.

## Actor file

It names the role this actor plays and the play it joins. Everything else comes from the director.

```yaml
# examples/tester.yaml
role: github.com/someone/tester@1.4.0
play: https://example.com/plays/habit-tracker/play.yaml
```

`role` is a role reference: `host/owner/name@version`, or a local folder such as `roles/tester`. A remote reference needs its version.

## Play file

It describes the play: the director, the stage, the cast, the script and the house rules.

```yaml
# examples/plays/habit-tracker/play.yaml
name: habit-tracker
director: wss://director.example.com
stage: git@github.com:alessio/habit-tracker.git
script: ./script.yaml
cast:
  product-owner: github.com/zanni-roles/product-owner@1.0.0
  tester: github.com/someone/tester@1.4.0
  coder: { role: github.com/zanni-roles/coder@1.0.0, seats: 1-4, host: local }
house_rules:
  budget: 20.00
  gates: [plan, release]
```

- **`cast`:** maps a seat name to a role reference, or to `{ role, seats, host }`.
- **`seats`:** a number (`2`) or a range (`1-4`). For a range, the director decides how many to cast, within it.
- **`host: local`:** the director starts these seats itself, on its own machine.
- **`director`:** can be left out, which means this machine runs the director.
- **`house_rules.budget`:** in USD, for the whole play.
- **`house_rules.gates`:** the moments that need a human's approval.

## Role manifest

`role.yaml` holds a role's Zanni fields. The character and instructions live in `AGENTS.md` beside it. See [Writing a role](writing-a-role.md).

```yaml
# examples/roles/tester/role.yaml
name: tester
version: 1.4.0
mission: Turn acceptance criteria into tests; explore the running app and report findings.
model: { needs: { tools: true, tier: judgement }, suggested: claude-sonnet-5-5 }
needs:
  stage_read: [vision.md, backlog/, spec/]
  stage_write: [tests/, findings/]
  tools: [browser, test-runner]
never:
  - edit application code
  - change priorities
outputs:
  findings/<item>.md: one finding per file, each with a failing test
```

**Write versions as text:** `1.4.0` works, and `"1.4"` is rejected as not being `major.minor.patch`. Unquoted, `1.4` is read as a number, and `zanni` tells you to quote it.
