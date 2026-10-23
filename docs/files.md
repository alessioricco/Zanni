# Zanni files

There is one command, `zanni <file>`. The kind of file comes from its keys, never from its name or a flag:

| Kind | Recognised by | What `zanni` would run | Full field list |
|---|---|---|---|
| Actor configuration | `role` and `play` | an actor: a zanni playing the role, joining the play | [spec: actor configuration](spec/actor-configuration.md) |
| Play file | `cast` | the play's director, running the play's script | [spec: play](spec/play.md) |
| Role manifest (`role.yaml`) | `mission` | nothing; it is validated | [spec: role package](spec/role-package.md) |

Scripts have their own format, specified in the [script spec](spec/README.md).

## Rules for every file

- **Unknown keys are errors.** A typo gets a "did you mean": a misspelled limit must never become a silent default.
- **Duplicate keys are errors.** Plain YAML would silently keep the last one.
- **No secrets in shared files.** Roles, scripts and plays are shared and published, so a key that looks like a secret (`api_key`, `token`, `password`, `client_secret`, …) is rejected at any depth. Only an actor configuration may hold credentials, and `zanni` protects it; see [Models and keys](models-and-keys.md).
- **Defaults everywhere.** A file only says what differs from the defaults. The spec pages list every field with its default.
- **Every problem at once.** `zanni` reports all the problems in a file in one go, each with its line.

## Actor configuration

One actor instance's own file. It names the role this instance plays and the play it joins, and (as the spec grows) its models and credentials. It stays on the actor's machine and never goes in a repository.

```yaml
# examples/tester.yaml
name: tester-1
role: github.com/someone/tester@1.4.0
play: https://example.com/plays/habit-tracker/play.yaml
```

`role` is a package reference: `host/owner/name@version`, or a local folder such as `roles/tester`. A remote reference needs its version.

## Play file

One production of a script: the script it performs, the director, a role for each of the script's parts, the stage, and the house rules.

```yaml
# examples/plays/habit-tracker/play.yaml
name: habit-tracker
script: github.com/someone/habit-tracker@1.0.0
director: wss://director.example.com
stage: git@github.com:alessio/habit-tracker.git
cast:
  product-owner: github.com/zanni-roles/product-owner@1.0.0
  tester: github.com/someone/tester@1.4.0
  coder: { role: github.com/zanni-roles/coder@1.0.0, seats: 1-4, host: local }
house_rules:
  budget: 20.00
  gates: [plan, release]
```

- **`script`:** a package reference to the script being performed. It is required.
- **`cast`:** maps each of the script's parts to a role reference, or to `{ role, seats, host }`.
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
