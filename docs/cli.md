# Command reference

```
zanni [-h] [--version] [--check] [--serve] [--listen HOST:PORT] [--play URL_OR_FILE] [--director FILE] [--update] [file]
zanni gate <play file or director URL> [approve | reject | resume] [--note NOTE]
```

There is one command, and it takes one file or folder. The file decides what runs; options only override what a file could say. `zanni gate` is the one exception: it talks to a running director, for its owner ([below](#zanni-gate)).

## Arguments and options

| | Meaning |
|---|---|
| `file` | An actor or director configuration, a play file, a role manifest, a script (`SCRIPT.md`), a lockfile, a rehearsal, or a folder. The kind comes from its keys ([Zanni files](files.md)). A folder holding `role.yaml` is checked as a whole role package; a folder holding `SCRIPT.md` is checked as that script. |
| `--check` | Only validate the file; never run anything: an actor configuration is not joined or run, a play is not started, and `--serve` serves nothing. For a play, it also lists every verifier command the director would run. |
| `--serve` | With a rehearsal: serve it to an actor on this machine or another (D29). Needs `ZANNI_JOIN_TOKEN` in the environment. |
| `--listen HOST:PORT` | With `--serve`, a play file or a director configuration: where the director listens, such as `0.0.0.0:8765` or `8765`. The default is `127.0.0.1` on a free port. |
| `--play URL_OR_FILE` | With an actor configuration: join this director or play instead of the one its `play` names (D36). A director uses it to start its local seats. |
| `--director FILE` | With a play file: the director's configuration. The default is `director.yaml` beside the play file (D34). |
| `--update` | With a play file or a director configuration: re-resolve every package's tag, rewrite `play.lock`, print what changed (commits, and verifier commands), and run nothing (D37). |
| `--version` | Print `zanni <version>` and exit. |
| `-h`, `--help` | Print the usage and exit. |

## What it does

1. **Read the file** as YAML. A syntax error is reported with its line.
2. **Work out the kind of file:** `role` + `play` is an actor configuration, `cast` is a play file, `mission` is a role manifest, `parts` (in Markdown frontmatter) is a script, `lock_version` is a lockfile.
3. **Validate it** against that kind's schema, and collect every problem. A play is also checked against its script when the script is local, and against `play.lock` when there is one. A role folder also has its `AGENTS.md`, skills and `mcp.json` checked.
4. **Print a summary** of what it would run, or the list of problems.

5. **Run it,** unless `--check` is given:
   - **A play file, or a director configuration,** runs the play on this machine: the director fetches and pins its packages, starts its local seats, waits for actors to join, and follows the script until the play stops ([Play: running a play](spec/play.md#running-a-play), [getting started](getting-started.md#running-a-play)).
   - **An actor configuration** joins the director its `play` names (D30): a director's URL, or a play file's `director`. When `play` is a [rehearsal](spec/rehearsal.md), a director is started for it on this machine, and the actor joins it the same way (D29).
   - **A rehearsal with `--serve`** starts a director serving it, and waits for an actor.

## `zanni gate`

```
zanni gate <play file or director URL>                          # show the play's state, and any pending gate
zanni gate <play file or director URL> approve [--note "…"]
zanni gate <play file or director URL> reject --note "…"
zanni gate <play file or director URL> resume [--note "…"]      # a play paused because the director's models failed
```

The owner of a play decides its gates, and resumes it when it is paused, from any machine that can reach its director (D38). The owner token comes from `ZANNI_OWNER_TOKEN` in the environment, never from the command line; it is the one in the director's configuration. With a play file, `zanni gate` finds the running director through `log/director.json` beside it, or else the play's `director`.

| Code | Meaning |
|---|---|
| `0` | Shown, or decided |
| `1` | Nothing to decide: no gate is pending, or the play isn't paused |
| `2` | No token, a wrong token (`not-authorised`), or no director to reach |

## Output

A valid file prints its summary on standard output, ending with `Valid.`. With `--check`, an actor configuration shows where it would join:

```
$ zanni --check examples/tester.yaml
Actor configuration: would start 'tester-1', playing a role in a play.
  role: github.com/someone/tester@1.4.0
  play: https://example.com/plays/habit-tracker/play.yaml
  models, in order:
    1. anthropic claude-sonnet-5-5
    2. ollama qwen3.8:27b, at ${OLLAMA_BASE_URL}, $0/$0 per million tokens
  credentials: ANTHROPIC_API_KEY (from the environment), GITHUB_TOKEN (from the environment), ZANNI_JOIN_TOKEN (from the environment)
  state: ~/.zanni/actors/tester-1
  joins: the director named in the play file https://example.com/plays/habit-tracker/play.yaml
Valid.
```

Credential values are never printed: a summary shows each credential's name and whether it is stored or comes from the environment (D15).

A file with problems prints them on standard error, one per line, in this form:

```
<file>, line <n>, <field path>: <what is wrong>; <what to change>
```

`<field path>` uses dots for nesting and brackets for list items, such as `cast.coder.seats` or `house_rules.gates[1]`. Problems with no single field leave it out, such as `play.yaml: is empty`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | The file is valid; the rehearsal passed; the actor's seat was released with `done`; or the play stopped as done, the rules agreeing |
| `1` | The rehearsal ran but didn't pass (a cue failed on every model, a `verify` check failed, or the seat was lost); the actor's seat ended for another reason, such as `no-heartbeat`; or the play stopped for any reason other than done (the budget, a gate, a pause nobody answered, the turn or round cap, the director's own reason, or Ctrl-C) |
| `2` | The file has problems, can't be read, or nothing could start: a missing credential, a model that can't call tools, a director that refused the actor or can't be reached, a missing `ZANNI_JOIN_TOKEN` or `ZANNI_OWNER_TOKEN`, a package that can't be fetched or doesn't match `play.lock`, no director configuration, an unpriced director under a budget, or no file given |

Scripts and CI can rely on these codes, and the [conformance tests](testing.md#conformance-tests) check them.
