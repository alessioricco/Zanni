# Zanni files

There is one command, `zanni <file>`. The kind of file comes from its keys, never from its name or a flag:

| Kind | Recognised by | What `zanni` would run | Full field list |
|---|---|---|---|
| Actor configuration | `role` and `play` | an actor: a zanni playing the role, joining the play | [spec: actor configuration](spec/actor-configuration.md) |
| Director configuration | `role: zanni:director` and `play` | the play's director, running its play | [spec: a director's configuration](spec/actor-configuration.md#a-directors-configuration) |
| Play file | `cast` | the play's director, running the play's script | [spec: play](spec/play.md) |
| Role manifest (`role.yaml`) | `mission` | nothing; it is validated | [spec: role package](spec/role-package.md) |
| Script (`SCRIPT.md`) | `parts`, in Markdown frontmatter | nothing; it is validated | [spec: script](spec/script.md) |
| Lockfile (`play.lock`) | `lock_version` | nothing; it is validated | [spec: play](spec/play.md#the-lockfile) |

`zanni` also takes a folder: a role folder (holding `role.yaml`) is checked as a whole package, and a script folder (holding `SCRIPT.md`) as its script.

## Rules for every file

- **Unknown keys are errors.** A typo gets a "did you mean": a misspelled limit must never become a silent default.
- **Duplicate keys are errors.** Plain YAML would silently keep the last one.
- **No secrets in shared files.** Roles, scripts and plays are shared and published, so a key that looks like a secret (`api_key`, `token`, `password`, `client_secret`, …) is rejected at any depth. Only an actor configuration may hold credentials, and `zanni` protects it; see [Models and keys](models-and-keys.md).
- **Defaults everywhere.** A file only says what differs from the defaults. The spec pages list every field with its default.
- **Every problem at once.** `zanni` reports all the problems in a file in one go, each with its line.

## Actor configuration

One actor instance's own file: the role this instance plays, the play it joins, the models it runs in order, and its credentials. It stays on the actor's machine and never goes in a repository.

```yaml
# examples/tester.yaml
name: tester-1
role: github.com/someone/tester@1.4.0
play: https://example.com/plays/habit-tracker/play.yaml
models:
  - provider: anthropic
    model: claude-sonnet-5-5
    credential: ANTHROPIC_API_KEY
  - provider: ollama
    model: qwen3.8:27b
    base_url: ${OLLAMA_BASE_URL}
    price: { input: 0, output: 0 }
credentials:
  ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
  GITHUB_TOKEN: ${GITHUB_TOKEN}
```

- **`models`:** tried in order: the next is used when one fails.
- **`credentials`:** may store values, as long as the file is private (`chmod 600`) and git doesn't track it. This example uses `${VAR}` references because it lives in a repository. See [Models and keys](models-and-keys.md).

`role` is a package reference: `host/owner/name@version`, or a local folder such as `roles/tester`. A remote reference needs its version.

## Play file

One production of a script: the script it performs, the director, a role for each of the script's parts, the stage, and the house rules.

```yaml
# examples/plays/habit-tracker/play.yaml
name: habit-tracker
script: github.com/someone/habit-tracker@1.0.0
director: https://director.example.com
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
- **`stage`:** the play's workspace. A git URL means a `git` stage and a folder path means a `folder` stage, or write `{ backend: …, … }`; see the [stage spec](spec/stage.md#in-the-play-file).
- **`cast`:** maps each of the script's parts to a role reference, or to `{ role, seats, host }`. When the script is local, `zanni` checks the cast against it.
- **`seats`:** a number (`2`) or a range (`1-4`), within the script's seats for the part. Left out, it takes the part's seats. For a range, the director decides how many to cast, within it.
- **`host: local`:** the director starts these seats itself, on its own machine.
- **`director`:** can be left out, which means this machine runs the director.
- **`house_rules.budget`:** in USD, for the whole play.
- **`house_rules.gates`:** which of the script's gates this play enforces.
- **`house_rules.max_seats_per_host`:** the most seats the director casts onto one machine.
- **`house_rules.gate_timeout`:** how long a gate, or a pause, may wait for a person, such as `2h`; with none, it waits.
- **`house_rules.max_director_turns`:** the most model turns the director takes in a round (default 30).
- **`verifiers`:** the play's own commands for its script's verifiers, such as `tests-pass: { command: [npm, test] }`.

Two more examples: `examples/plays/newsroom/play.yaml` uses a local script, a folder stage and a `play.lock`; `examples/plays/slug-kata/` is a whole play you can run, with its director's configuration and its local seats ([getting started](getting-started.md#running-a-play)).

## Director configuration

The director is an actor too: its configuration is an actor configuration whose `role` is `zanni:director`, Zanni's built-in director role. It sits beside the play as `director.yaml`, or is named with `--director`.

```yaml
# examples/plays/slug-kata/director.yaml
name: director
role: zanni:director
play: ./play.yaml
models:
  - provider: anthropic
    model: claude-haiku-5-5
  - provider: ollama
    model: qwen3.8:27b
    base_url: ${OLLAMA_BASE_URL}
    price: { input: 0, output: 0 }
credentials:
  ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
  ZANNI_JOIN_TOKEN: ${ZANNI_JOIN_TOKEN}     # the play's join token: actors present it
  ZANNI_OWNER_TOKEN: ${ZANNI_OWNER_TOKEN}   # the play's owner token: zanni gate presents it
seats:
  tester: [./tester-1.yaml]
  coder: [./coder-1.yaml, ./coder-2.yaml]
```

- **`models`:** the director's own, in order. Nothing picks a model for you: the director runs on what this file lists, and under a budget each must have a price.
- **`seats`:** the actor configurations the director starts as local seats, one file per seat. It reads only their `name` and `role`, never their credentials.

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
