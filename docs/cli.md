# Command reference

```
zanni [-h] [--version] [file]
```

There is one command, and it takes one file. The file decides what runs; options only override what a file could say.

## Arguments and options

| | Meaning |
|---|---|
| `file` | An actor file, a play file or a role manifest. The kind comes from its keys ([Zanni files](files.md)). |
| `--version` | Print `zanni <version>` and exit. |
| `-h`, `--help` | Print the usage and exit. |

## What it does

1. **Read the file** as YAML. A syntax error is reported with its line.
2. **Work out the kind of file:** `role` + `play` is an actor file, `cast` is a play file, `mission` is a role manifest.
3. **Validate it** against that kind's schema, and collect every problem.
4. **Print a summary** of what it would run, or the list of problems.

It doesn't start anything yet. Running actors and directors comes in later milestones ([roadmap](../ROADMAP.md)).

## Output

A valid file prints its summary on standard output, ending with `Valid.`:

```
Actor file: would start an actor that joins a play.
  role: github.com/someone/tester@1.4.0
  play: https://example.com/plays/habit-tracker/play.yaml
Valid. Nothing was started: running files comes in a later version (see ROADMAP.md).
```

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
