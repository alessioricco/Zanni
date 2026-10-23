# Command reference

```
zanni [-h] [--version] [file]
```

There is one command, and it takes one file or folder. The file decides what runs; options only override what a file could say.

## Arguments and options

| | Meaning |
|---|---|
| `file` | An actor configuration, a play file, a role manifest, a script (`SCRIPT.md`), a lockfile, or a folder. The kind comes from its keys ([Zanni files](files.md)). A folder holding `role.yaml` is checked as a whole role package; a folder holding `SCRIPT.md` is checked as that script. |
| `--version` | Print `zanni <version>` and exit. |
| `-h`, `--help` | Print the usage and exit. |

## What it does

1. **Read the file** as YAML. A syntax error is reported with its line.
2. **Work out the kind of file:** `role` + `play` is an actor configuration, `cast` is a play file, `mission` is a role manifest, `parts` (in Markdown frontmatter) is a script, `lock_version` is a lockfile.
3. **Validate it** against that kind's schema, and collect every problem. A play is also checked against its script when the script is local, and against `play.lock` when there is one. A role folder also has its `AGENTS.md`, skills and `mcp.json` checked.
4. **Print a summary** of what it would run, or the list of problems.

It doesn't start anything yet. Running actors and directors comes in later milestones ([roadmap](../ROADMAP.md)).

## Output

A valid file prints its summary on standard output, ending with `Valid.`:

```
Actor configuration: would start 'tester-1', playing a role in a play.
  role: github.com/someone/tester@1.4.0
  play: https://example.com/plays/habit-tracker/play.yaml
  models, in order:
    1. anthropic claude-sonnet-5-5
    2. ollama qwen3.8:27b, at ${OLLAMA_BASE_URL}, $0/$0 per million tokens
  credentials: ANTHROPIC_API_KEY (from the environment), GITHUB_TOKEN (from the environment)
  state: ~/.zanni/actors/tester-1
Valid. Nothing was started: running files comes in a later version (see ROADMAP.md).
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
| `0` | The file is valid |
| `2` | The file has problems, can't be read, or no file was given |

Scripts and CI can rely on these codes, and the [conformance tests](testing.md#conformance-tests) check them.
