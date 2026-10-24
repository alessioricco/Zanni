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
```

Seats are a number of at least 1, or a range written smaller number first. A `git` stage takes `url` and `branch`; a `folder` stage takes `path`.

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

### "is a remote role"

```
github.com/someone/slug-tester@0.1.0: is a remote role, and fetching roles comes with milestone 4; clone it and use the local folder, e.g. role: ./roles/tester
```

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

### "ZANNI_JOIN_TOKEN isn't in the actor configuration's `credentials`"

```
notoken.yaml: ZANNI_JOIN_TOKEN isn't in the actor configuration's `credentials`; add it, e.g. ZANNI_JOIN_TOKEN: ${ZANNI_JOIN_TOKEN}, with the play's join token in the environment; nothing was started.
```

An actor joining a director needs the play's join token. Add it to `credentials`, as a `${ZANNI_JOIN_TOKEN}` reference or a stored value. When the reference is there but the environment doesn't set it, the message is `${ZANNI_JOIN_TOKEN} has no value` instead.

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

## Role folders

`zanni <role folder>` checks the whole package.

```
roles/tester/AGENTS.md: is missing or empty; write the role's character and instructions in AGENTS.md
roles/tester/role.yaml, line 5, needs.tools[0]: "browser" is not a server in mcp.json; add a `browser` server to mcp.json
roles/tester/skills/write-test/SKILL.md, line 2, name: "write-tests" doesn't match its folder "write-test"; rename the folder or the skill so they match
roles/tester/mcp.json, line 5, mcpServers.gh.env.GITHUB_TOKEN: holds a literal secret, and a role is shared, so it never holds secrets; write ${GITHUB_TOKEN} and give the value in the actor configuration
```

- **`needs.tools`:** each name must be a server in the role's `mcp.json`.
- **Skills:** a skill's `name` must match its folder, as the Agent Skills spec requires.
- **Secrets in `mcp.json`:** write them as `${NAME}`. Each actor then supplies its own value, from its configuration's `credentials` or its environment.

## Still stuck?

[Open an issue](https://github.com/alessioricco/Zanni/issues). Include the file, the exact output, and `zanni --version`.
