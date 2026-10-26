# Troubleshooting

Each problem `zanni` reports already says what to change. This page explains the common ones. Every message below was copied from a real run.

## Any file

### "is not an actor configuration, a play file, a role manifest, a script or a lockfile"

```
notes.yaml: is not an actor configuration, a play file, a role manifest, a script or a lockfile; each kind needs these fields: actor configuration: `play` and `role`; play file: `cast`; role manifest: `mission`; script: `parts`; lockfile: `lock_version`
```

`zanni` recognises a file by its keys. Add the key that marks the kind you meant. If you misspelled one of those keys, `zanni` points at it instead:

```
role.yaml, line 3, mision: is not a known field; did you mean `mission`?
```

### "looks like more than one kind of file"

The file has the marking keys of two kinds, such as `role` and `play` and also `cast`. An actor configuration and a play file are separate files: one belongs to an actor's machine, the other to the play. Split it in two.

### "is not a known field"

```
play.yaml, line 9, cast.coder.hots: is not a known field; did you mean `host`?
```

Unknown keys in Zanni's own formats are always errors, so a typo can never silently turn into a default. Fix the spelling, or remove the key. The full field lists are in the [spec](spec/README.md).

### "looks like a secret"

```
play.yaml, line 7, house_rules.token: looks like a secret, and only an actor configuration's `credentials` may hold one; remove it; secrets belong in an actor configuration's `credentials`, or the environment
```

Roles, scripts and plays are shared, so they never hold secrets. Move the value to the `credentials` of the actor configuration that needs it, or to the environment; see [Models and keys](models-and-keys.md). A key counts as a secret when one of its words is `key`, `token`, `secret` or `password`, wherever it appears.

### "has no version"

```
tester.yaml, line 5, role: "github.com/someone/tester" has no version; write it as github.com/someone/tester@1.0.0, with the version you want
```

A remote package reference needs a version: `github.com/someone/tester@1.4.0`. A local folder needs none: `roles/tester`.

### "was read as a number"

```
role.yaml, line 2, version: 1.4 was read as a number; write the version in quotes as major.minor.patch, e.g. "1.4.0"
```

YAML reads `1.4` as a number. Write versions with three parts, which YAML keeps as text (`1.4.0`), or put them in quotes.

### "appears twice"

```
play.yaml, line 2, name: appears twice; keep one of the two entries
```

Plain YAML would silently keep the last value, so `zanni` refuses instead.

### "is not valid YAML"

```
play.yaml, line 2: is not valid YAML: mapping values are not allowed here; check the indentation and the quotes on this line and the one before
```

This is usually indentation: nested fields need the same number of spaces, and tabs aren't allowed. Text that contains `: ` needs quotes.

## Actor configurations

### "holds credentials, but other users can read this file"

```
tester.yaml, line 6, credentials: holds credentials, but other users can read this file (mode 644); run: chmod 600 tester.yaml
```

A configuration that stores credentials must be private to you, as SSH requires of private keys. Run the `chmod` it gives. A configuration whose credentials are all `${VAR}` references stores nothing, so this check doesn't apply to it.

### "holds credentials, but git tracks this file"

Actor configurations that store credentials never belong in a repository. Untrack the file with `git rm --cached <file>`, add it to `.gitignore`, and if it was ever pushed, change the credentials. Or use `${VAR}` references instead of values.

### "models: is required but missing"

```
nomodels.yaml, line 1, models: is required but missing; add a `models:` line
```

Every actor runs at least one model, set in its own configuration (D11):

```yaml
models:
  - { provider: ollama, model: qwen3.8:27b }
```

### "an openai-compatible model needs a `base_url`"

```
tester.yaml, line 4, models[0]: an openai-compatible model needs a `base_url`; add the server's URL, e.g. http://gpu-box:8000/v1
```

`openai-compatible` can be any server, so `zanni` needs its address.

### "is not a tool the role needs"

```
coder-1.yaml, line 6, tools.browser: "browser" is not a tool the role needs; bind only tools in the role's needs.tools: workspace
```

An actor's `tools` may only replace servers its role asks for, by the same name (D53). Use the name from the role's `needs.tools`, such as `workspace`. A role whose folder isn't on this machine is checked when the actor fetches it.

### "holds a secret's value, which belongs only in `credentials`"

```
coder-1.yaml, line 8, tools.coding-engine.env.ENGINE_API_KEY: holds a secret's value, which belongs only in `credentials`; write ${ENGINE_API_KEY} here, and put the value under `credentials`
```

A tool the actor brings may take a key, but only as a `${NAME}` reference; the value goes under `credentials`, where `zanni` protects it ([Models and keys](models-and-keys.md#tools-an-actor-brings-and-their-keys)).

### "has no tools to bind and runs no workspace"

```
director.yaml, line 5, tools: the built-in role zanni:director has no tools to bind and runs no workspace; remove `tools`
```

`tools` and `workspace` belong in a seat's configuration. The director and verifier seats run Zanni's built-in roles, which need neither.

## Plays

### "is not a part in the script", "doesn't cast the script's part"

```
play.yaml, line 6, cast.editor: is not a part in the script; the script's parts are: writer, reviewer
play.yaml, line 4, cast: doesn't cast the script's part `writer`; add `writer:` with a role to cast
```

When the play's script is local, `zanni` checks the play against it. `cast` names the script's parts. Every part the script doesn't mark `optional` must be cast.

### "is outside the script's … for this part"

```
play.yaml, line 5, cast.writer.seats: 1-5 is outside the script's 1-3 for this part; use seats within 1-3, or leave `seats` out to use 1-3
```

A play may narrow a part's seats, never widen them.

### "is not one of the script's gates"

```
play.yaml, line 7, house_rules.gates[1]: "release" is not one of the script's gates; use one of: publish
```

A play enforces gates the script defines; it can't invent new ones.

### "script: … does not exist"

```
play.yaml, line 2, script: "../fixtures/scripts/nope" does not exist; check the path, relative to the play file
```

A local `script:` is relative to the play file, and may point to `SCRIPT.md` or the folder holding it.

### Seats and the stage

```
play.yaml, line 4, cast.coder.seats: the range 4-1 goes down; write the smaller number first: 1-4
play.yaml, line 3, stage: a git stage needs a `url`; add the repository, e.g. url: git@github.com:you/app.git
play.yaml, line 8, stage: an mcp stage needs a `url`, the server's http(s) endpoint, e.g. url: http://docs.internal:8800/mcp
play.yaml, line 8, stage.push: is "sometimes"; use one of: 'approved' or 'always'
```

Seats are a number of at least 1, or a range written smaller number first. A `git` stage takes `url`, `branch` and `push`; a `folder` stage takes `path`; an `mcp` stage takes `url`, an `http` or `https` URL ([stage spec](spec/stage.md#in-the-play-file)).

### "is more than the script's stop.max_rounds"

```
play.yaml, line 7, house_rules.max_rounds: 3 is more than the script's stop.max_rounds, 2; use 2 or fewer; a play may lower the script's limit, never raise it
```

A play may lower its script's round limit, never raise it. To go on after a run's last round, grant one more at the release gate (`zanni gate <play> approve --another-round`), or continue the run later (`zanni <play> --continue <run-id>`) ([getting started](getting-started.md#the-software-team)).

## Scripts

### "a script is a Markdown file"

```
script.yaml: looks like a script, but a script is a Markdown file; put these fields between --- lines at the top of a .md file, then the prose
```

A script is `SCRIPT.md`: the checked fields between `---` lines at the top, then prose for the director. See [Writing a script](writing-a-script.md).

### "has no prose after the frontmatter"

```
SCRIPT.md, line 8: has no prose after the frontmatter; describe the acts and scenes for the director below the --- line
```

The prose is what the director follows, so it is required.

### "is not a file in the script's folder"

```
SCRIPT.md, line 12, verifiers.tests-cover-criteria.files[0]: "checks/criteria.py" is not a file in the script's folder; add it to …/my-script, or fix the path, relative to the script's folder
```

A verifier's `files` are check files shipped in the script's own folder, run from `${ZANNI_SCRIPT}` (D55). Write each path relative to the folder holding `SCRIPT.md`, with `/`, and never leaving it: `../criteria.py` is refused too.

## Running a rehearsal

### "can't call tools natively"

```
gemma-native.yaml: ollama gemma3:4b can't call tools natively (its capabilities: completion, vision), and this role needs tools; add `tool_format: text` to its model entry; nothing was started.
```

`zanni` asked the Ollama server what the model can do, before running. Add `tool_format: text` to that model entry, or use a model that calls tools.

### "has no value"

```
slug-tester.yaml: ${NOT_SET_ANYWHERE} has no value: add NOT_SET_ANYWHERE to the actor configuration's `credentials`, or set it in the environment; nothing was started.
```

A `${NAME}` in the configuration, or in the role's `mcp.json`, has no value. `zanni` reads the environment, not a `.env` file; load one with `set -a; . ./.env; set +a`.

When only some models can't be resolved, such as a cloud fallback on a machine with no cloud key, the actor runs with the others and says which it skipped:

```
Skipping anthropic claude-haiku-5-5: ${ANTHROPIC_API_KEY} has no value: add ANTHROPIC_API_KEY to the actor configuration's `credentials`, or set it in the environment
```

The error above appears only when no model is left.

### "has no tag"

A remote role or script resolves to a git tag `vX.Y.Z` or `X.Y.Z` (for a package in a subfolder, `path/vX.Y.Z` first). The message lists the nearest tags the repository has:

```
example.test/someone/tester@1.2.0: https://example.test/someone/tester.git has no tag v1.2.0 or 1.2.0; the nearest tags are: 1.1.0; check the reference and that git can reach it, or use a local folder
```

Use a version that exists, or ask the package's author to tag it. Zanni fetches with your own `git`, so a private repository needs your SSH key or credential helper to work with `git ls-remote <url>` first; git never asks for a password while zanni runs it.

### "Google models need the `google` extra"

```
google.yaml: google gemini-x: Google models need the `google` extra; install it with: uv sync --extra google; nothing was started.
```

### A model failed, and the next one ran

```
    ollama qwen3.8:27b failed (error); trying the next model
```

The actor moved to the next model in its configuration, because the failure's reason (`error`, `timeout`, `rate-limit`, `context` or `refusal`) is in that entry's `fall_back_on`. The run log records a `fallback` event with the details.

### "Rehearsal FAILED" with "no tests ran"

The actor ran, but its work didn't pass the rehearsal's `verify` checks. Look at the stage copy and `log.jsonl` in the folder the last line names. In the recorded runs, this is how a small model's broken tool block was caught ([docs/runs/milestone-2.md](runs/milestone-2.md)).

## Joining a director

### "Refused: not-authorised"

```
Refused: not-authorised: the join token is missing, or isn't this play's
```

The actor's `ZANNI_JOIN_TOKEN` isn't the one the director was started with. Give both sides the same value. The actor exits with code 2; the director keeps waiting for an actor that fits.

### "Refused: hash-mismatch"

```
Refused: hash-mismatch: the actor's slug-tester has hash sha256:ce04…6715, and this rehearsal's package has sha256:9d59…f097: they are different versions of the role
```

A served rehearsal accepts only the role it belongs to, byte for byte. Some file in the actor's copy of the role differs from the director's. Copy the role again, or check out the same version on both machines. A `role-mismatch` refusal means the actor plays a different role altogether.

### "couldn't fetch the director's card"

```
nodirector.yaml: couldn't join: couldn't fetch the director's card from http://127.0.0.1:9: Network communication error fetching agent card from http://127.0.0.1:9/.well-known/agent-card.json: All connection attempts failed
```

Nothing answered at the configuration's `play` address. Check that the director is running, and that its address and port are right. From the actor's machine, `curl http://<director's address>:<port>/.well-known/agent-card.json` should print the card. If it doesn't, the director may be listening on `127.0.0.1` only (serve with `--listen 0.0.0.0:<port>`), or a firewall on its machine may be blocking the port.

### "ZANNI_JOIN_TOKEN isn't in the actor configuration's `credentials` or the environment"

```
notoken.yaml: ZANNI_JOIN_TOKEN isn't in the actor configuration's `credentials` or the environment; add it, e.g. ZANNI_JOIN_TOKEN: ${ZANNI_JOIN_TOKEN}, with the play's join token in the environment; nothing was started.
```

An actor joining a director needs the play's join token: in `credentials`, as a `${ZANNI_JOIN_TOKEN}` reference or a stored value, or else in its environment (D36). When the reference is there but the environment doesn't set it, the message is `${ZANNI_JOIN_TOKEN} has no value` instead.

### "ZANNI_JOIN_TOKEN isn't set", when serving

```
smoke.yaml: ZANNI_JOIN_TOKEN isn't set; set it to the play's join token, and give actors the same value in their configuration's credentials; nothing was started.
```

`--serve` reads the join token from its environment. Export it before serving.

### "is not an address zanni can join"

```
scheme.yaml, line 3, play: "ws://127.0.0.1:9" is not an address zanni can join; use an http:// or https:// URL, a play file or a rehearsal (D30)
```

A director's address is an `http://` or `https://` URL (D30).

## Running a play

### "no director configuration"

```
plays/slug-kata/play.yaml: no director configuration: there is no --director, and no plays/slug-kata/director.yaml. Write one beside the play (role: zanni:director, play: ./play.yaml, its models and credentials); see examples/plays/slug-kata/director.yaml; nothing was started.
```

A play's director needs its own models and credentials, and a play never chooses models. Write `director.yaml` beside the play, or name one with `--director` (D34). Nothing else is looked for, because its tokens belong to this play.

### "ZANNI_JOIN_TOKEN isn't in the director configuration's `credentials` (or has no value)"

```
plays/slug-kata/play.yaml: ZANNI_JOIN_TOKEN isn't in the director configuration's `credentials` (or has no value); add ZANNI_JOIN_TOKEN: ${ZANNI_JOIN_TOKEN}, and set it in the environment (D34); nothing was started.
```

The director needs the play's join token (actors present it) and its owner token (`zanni gate` presents it). The example's `director.yaml` has both as `${VAR}` references: set them in the environment, for example with `export ZANNI_JOIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")`, and the same for `ZANNI_OWNER_TOKEN`.

### "Skipping the director's …"

```
Skipping the director's ollama qwen3.8:27b: ${OLLAMA_BASE_URL} has no value: add OLLAMA_BASE_URL to the actor configuration's `credentials`, or set it in the environment
```

Not an error: one of the director's models can't be used on this machine, so the director runs on the others. It starts only if at least one is left.

### "the director's models aren't all priced"

The play has a budget, and one of the director's models has no price, so its own cost would be unknown (D39). Add `price:` to that model's entry; for a local model, `price: { input: 0, output: 0 }`.

### "someone moved the tag"

```
plays/my-play/play.yaml: example.test/someone/kata@1.0.0: its tag v1.0.0 now points to 20d32853543dc5afeb369568795f1b5ee1e7dcf1, and play.lock pins edcdaaea19a9510c02e8cee40312ce619599a222; someone moved the tag. Check with the package's author, then run --update to accept the new commit; nothing was started.
```

`play.lock` pins each remote package to the commit its tag pointed to when the lock was written, so a play runs the same code every time (D37). A tag that now points elsewhere is refused. Ask the package's author why it moved. If you accept the new code, run `zanni play.yaml --update`, which rewrites `play.lock`, prints what changed (verifier commands included), and runs nothing.

### "Refused: unpriced"

```
Joining the play 'slug-kata' (script ../../scripts/slug-kata) at http://127.0.0.1:…
Refused: unpriced: this play has a budget, and the actor's models aren't all priced, so its cost would be unknown; add `price:` to each model entry in its configuration (D7)
```

Printed by an actor, which exits with code 2. Under a budget, every model an actor may use needs a price: a published one, or `price:` in its configuration; for a local model, `price: { input: 0, output: 0 }` (D39). A local seat refused this way isn't restarted, since a restart wouldn't change the answer (D50). Its part waits for an actor to join, until `cast_timeout`. So fix the configuration, and run the play again.

### "Still missing after the cast_timeout"

```
Waiting for actors to join: coder, tester, the verifier seat ci-box
Still missing after the cast_timeout (15 s): the verifier seat ci-box; the play stops
The play stopped: uncastable. Rounds: 1; spent $0.0000; verdicts: none.
```

Before its first turn, the director waits for every part's minimum seats, and for every verifier seat a verifier `runs_on`. After losing a seat, it waits the same way for a replacement. When `cast_timeout` (default `10m`) passes with one still missing, the play stops with reason `uncastable`, exit code 1 (D50). Check what's missing:
- **A local seat:** its own output, in the play's `log/<run-id>-seats/` folder. A seat refused at join, such as `unpriced`, isn't restarted.
- **An actor or a verifier seat from another machine:** start it, with the director's address and the right token. It can start before the director: run it in a loop that retries while it can't connect (exit code 2), as in [docs/runs/milestone-5.md](runs/milestone-5.md).

### "stopped at its budget", and reports with `over-budget`

```
  cue r1-c1: specify
    stopped at its budget on ollama qwen3.8:27b: 4 tool calls, 1238 in / 152 out tokens, cost $0.1390
```

Not an error: the actor reached its cue's budget and ended the cue there, reporting `over-budget` (D39). The director gives each cue a share of what is left of the play's budget. The actor checks after each model response, so one response can overshoot the cue's budget, by a lot when the budget is small. If cues keep stopping, the play's budget is too small for its models: raise `house_rules.budget`, or use cheaper models. When nothing is left to reserve, the play stops with reason `budget` (exit code 1).

### "there is no run … in …/log"

```
plays/software-mini-python/play.yaml: there is no run '20261025T100000Z' in …/plays/software-mini-python/log; the play's runs are: 20261025T200034Z; nothing was started.
```

`--continue` takes the id of an earlier run of the same play: the name of its log file, `log/<run-id>.jsonl`, which the message lists. Continue from the same play folder that ran it.

### "no director is running for …", from `zanni gate`

```
no director is running for plays/slug-kata/play.yaml: there is no plays/slug-kata/log/director.json, and the play names no `director`; start it with zanni play.yaml, or give the director's URL
```

`zanni gate` finds a running director through `log/director.json` beside the play, which the director writes while it runs. Run it on the director's machine with the play file, or anywhere with the director's URL.

### "ZANNI_OWNER_TOKEN isn't set", from `zanni gate`

```
ZANNI_OWNER_TOKEN isn't set; set it to the play's owner token (the director's configuration has the same one). It never goes on the command line.
```

Set the owner token in the environment where you run `zanni gate`: the same value as the director's `ZANNI_OWNER_TOKEN`. A join token, or an actor's seat token, gets `not-authorised` instead (D38).

### "not-authorised", from `zanni gate`

```
not-authorised: this needs the play's owner token (ZANNI_OWNER_TOKEN), not a join or seat token
```

The `ZANNI_OWNER_TOKEN` in your environment isn't the one in the director's configuration. Set the same value in both (D38). Exit code 2.

### "--another-round goes with approve", from `zanni gate`

```
--another-round goes with approve: it approves the gate and grants one more round.
```

One more round is granted only by approving a gate. Exit code 2. A play with no round limit (neither its `house_rules.max_rounds` nor the script's `stop.max_rounds`) has no round to add: the director answers "this play has no round limit, so there is no round to add; approve without --another-round".

### "Nothing decided", from `zanni gate`

```
Nothing decided: the play is at a gate, not paused; use approve or reject
```

`resume` is for a paused play, and `approve` or `reject` for a play waiting at a gate. `zanni gate <play>` with no decision shows which it is. Exit code 1.

## Stages

### "couldn't clone"

```
plays/slug-kata-git/play.yaml: couldn't clone …/plays/slug-kata-git/remote.git (branch main): repository '…/plays/slug-kata-git/remote.git' does not exist; nothing was started.
```

The director clones a git stage's `url` before anything starts, using your own git and its credentials. Check that `git clone <url>` works on the director's machine. The example's remote is made by `python3 make-remote.py` in its play folder ([getting started](getting-started.md#a-play-on-a-git-stage)). Git never prompts for a password while the director runs it, so a private repository needs an SSH key or a credential helper that works without asking.

### "couldn't push"

```
  couldn't push zanni/slug-kata-git/20261025T031931Z (the approved gate plan): '…/nowhere.git' does not appear to be a git repository; the work stays in …/plays/slug-kata-git/log/20261025T031931Z-stage
```

Not fatal: the play goes on, and every commit stays in the run's clone. Fix git's access to the remote, then push the run's branch yourself: `git -C <the run's clone> push origin <the branch>`.

### "not pushed (push: approved, and the play didn't finish)"

```
The run's work is on the branch zanni/slug-kata-git/20261025T031756Z, in …/log/20261025T031756Z-stage, not pushed (push: approved, and the play didn't finish). To publish it: git -C …/log/20261025T031756Z-stage push origin zanni/slug-kata-git/20261025T031756Z
```

Not an error. With `push: approved`, the default, the remote gets only work that passed an approved gate, or a finished play. Run the printed command to publish the rest, or set `push: always` in the play's `stage` to push at the end of every run ([stage spec](spec/stage.md#pushing)).

### "couldn't reach the stage's server"

```
plays/release-notes/play.yaml: couldn't reach the stage's server at http://127.0.0.1:8800/mcp: couldn't connect to the stage at http://127.0.0.1:8800/mcp: ConnectError: All connection attempts failed; nothing was started.
plays/release-notes/play.yaml: couldn't reach the stage's server at http://127.0.0.1:8800/mcp: couldn't connect to the stage at http://127.0.0.1:8800/mcp: the server refused the token (HTTP 401); nothing was started.
```

- **"All connection attempts failed":** nothing answers at the play's `stage.url`. Start the stage server first, or fix the address.
- **"refused the token":** the director's `ZANNI_STAGE_TOKEN` isn't the server's. Give both the same value.

### "ZANNI_STAGE_TOKEN isn't in the director configuration's `credentials`"

```
plays/release-notes/play.yaml: this play's stage is an mcp server, and ZANNI_STAGE_TOKEN isn't in the director configuration's `credentials` (or has no value); add ZANNI_STAGE_TOKEN: ${ZANNI_STAGE_TOKEN}, with the server's token in the environment (D47); nothing was started.
```

Only the director presents the stage server's token; the play file never holds it. Set it in the environment where you start the director.

### "Paused: the stage's server … isn't answering"

```
  report from editor-1 on r1-c2: failed, cost $0.000206
Paused: the stage's server at http://127.0.0.1:49174/mcp isn't answering: couldn't connect to the stage at http://127.0.0.1:49174/mcp: ConnectError: All connection attempts failed. Resume with: zanni gate <play> resume
Resumed.
```

The stage server stopped answering during the play. The director retried, then paused the play; the cue that met it ended as `failed`. Start the server again, on the same address and storage, then run `zanni gate <play> resume`. The director goes on from where it was. Unanswered, the pause ends the play after `gate_timeout`, if one is set.

### "Refused: not-authorised", from a verifier seat

```
Refused: not-authorised: a verifier seat joins with the play's verifier token (ZANNI_VERIFIER_TOKEN), never with the join token
```

A verifier seat presents `ZANNI_VERIFIER_TOKEN`, the director's own, never the join token: the director trusts a verifier seat's exit codes, so actors can't take its place (D45). Its name must also be listed under `verifier_seats` in the director's configuration.

### "the verifier seat … isn't connected"

```
  verifier notes-structure: FAILED (on checker-remote)
```

The play's log gives the reason, in the `verdict` event's `detail`: "the verifier seat checker-remote isn't connected, so notes-structure couldn't run". The verifier `runs_on` a verifier seat that isn't cast now. At the start, the director waits for it within `cast_timeout`. If it's lost later, the verifier fails until the seat joins again: restart it, with its verifier token.

## Role folders

`zanni <role folder>` checks the whole package.

```
roles/tester/AGENTS.md: is missing or empty; write the role's character and instructions in AGENTS.md
roles/tester/role.yaml, line 5, needs.tools[0]: "browser" is not a server in mcp.json; add a `browser` server to mcp.json
roles/tester/skills/write-test/SKILL.md, line 2, name: "write-tests" doesn't match its folder "write-test"; rename the folder or the skill so they match
roles/tester/mcp.json, line 5, mcpServers.gh.env.GITHUB_TOKEN: holds a literal secret, and a role is shared, so it never holds secrets; write ${GITHUB_TOKEN} and give the value in the actor configuration
roles/coder/mcp.json, line 3, mcpServers.shell: "zanni:shell" is not a server Zanni ships; use zanni:workspace
```

- **`needs.tools`:** each name must be a server in the role's `mcp.json`.
- **Skills:** a skill's `name` must match its folder, as the Agent Skills spec requires.
- **Secrets in `mcp.json`:** write them as `${NAME}`. Each actor then supplies its own value, from its configuration's `credentials` or its environment.
- **Built-in servers:** `zanni:workspace` is the only server Zanni ships, and takes no `args` or `env` ([Writing a role: tools](writing-a-role.md#tools-and-the-workspace)).

## Still stuck?

[Open an issue](https://github.com/alessioricco/Zanni/issues). Include the file, the exact output, and `zanni --version`.
