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
