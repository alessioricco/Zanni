# Writing a role

A role is a package describing a persona: who it is, what it knows how to do, which tools it needs, and what it may touch. A zanni is an empty shell until it is given a role, so adding a role needs no code. A role holds capabilities only: names, models and credentials belong to each actor's configuration.

> **Status:** actors play roles today, in rehearsals and in plays. `zanni` validates a whole role folder: `role.yaml`, `AGENTS.md`, the skills, `mcp.json` and the rehearsals. The repository's examples include the software team's six roles in `examples/roles/` (`product-owner`, `architect`, `ui-designer`, `tester`, `developer-lead`, `coder`), each with a rehearsal.

## The folder

```
roles/tester/
  role.yaml       # Zanni's fields
  AGENTS.md       # character and instructions
  skills/
    write-test/
      SKILL.md    # one skill per folder
  mcp.json        # the MCP servers the role expects
  notes/          # lessons, private to the role
```

Only `role.yaml` is Zanni's own format. The other files follow their standards unchanged.

## 1. `role.yaml`: what the role asks for

```yaml
# examples/roles/tester/role.yaml
name: tester
version: 0.1.0
mission: Turn acceptance criteria into tests; explore the running app and report findings.
model: { needs: { tools: true, tier: coding } }
needs:
  stage_read: ["/"]          # the whole stage: the project's own files, such as its .gitignore
  stage_write: [tests/, findings/, reviews/]
  tools: [workspace]
never:
  - edit application code
  - change priorities
  - change a test to make it pass
outputs:
  findings/<item>.md: one finding per file, each with a failing test under tests/findings/
```

- **`needs` are requests, not grants.** The play decides what to grant, and the stage enforces what a seat may read and write. A role can't give itself more access.
- **`never` is guidance for the model, not a limit.** The real limits are the stage's permissions and the verifiers. Write `never` rules anyway: they keep the role on task.
- **`model.needs` says what kind of model the role needs, not which one.** The model is chosen in each actor's configuration; `model.needs` and `suggested` are hints for whoever writes it. A role never requires a particular model or vendor.

- **`needs.tools` names the tools the role needs,** and each must be a server in its `mcp.json`, its default. An actor may bring its own server for any of them ([below](#tools-and-the-workspace)).
- **`outputs` must sit inside `needs.stage_write`.**
- **`model.needs.tier`** is a free label. The reference roles use `judgement`, `coding`, `planning` and `basic`.
- **Name no stack or product.** A coder role writes code in whatever stack the project's own files name; a role never says "Python" or names a coding engine. What a role needs, it names by what it does.

Check the manifest alone, or the whole folder:

```bash
uv run zanni roles/tester/role.yaml
uv run zanni roles/tester           # also checks AGENTS.md, skills and mcp.json
```

Every field, with its type and default, is in the [role package spec](spec/role-package.md).

## 2. `AGENTS.md`: the character

This is plain Markdown: who the role is, how it works, and what it hands back. It becomes the actor's instructions. If you use Claude Code on the role itself, a `CLAUDE.md` can point to it.

```markdown
# Tester

You turn acceptance criteria into tests. You write tests, never application code.

- Read the spec before writing anything.
- One test per acceptance criterion, named after it.
- When you are done, reply with the path of the file you wrote and one line on what it checks.
```

**No vendor tricks.** Don't write instructions that only work for one model, and don't name a model or a vendor. The same role must run on a local model and a cloud model.

## 3. `skills/`: what it knows how to do

Each skill is a folder with a `SKILL.md`, in the [Agent Skills](https://agentskills.io) format: YAML frontmatter with `name` (matching the folder's name) and `description`, then the instructions.

```markdown
---
name: write-test
description: How to write one pytest test for one acceptance criterion. Load before writing any test.
---

# Write a test

1. Find the criterion's exact input and expected output in the spec.
2. Write one function `test_<criterion_id>` with a single `assert`.
3. Save it as `tests/test_<criterion_id>.py`.
```

Skills load on demand. The actor sees each skill's name and description, and reads the full skill only when it needs it. So the `description` decides when a skill is used: say what it does and when to load it.

The `skill-creator` skill helps write and test skills; see [Coding agents and skills](agent-skills.md).

## 4. `mcp.json`: the tools it expects

Zanni has no built-in tools. A role lists the MCP servers it expects, in the standard `mcpServers` format that Claude Desktop, Claude Code and Cursor also use:

```json
{
  "mcpServers": {
    "verifier": {
      "command": "uv",
      "args": ["run", "python", "-m", "my_verifier"],
      "env": { "STAGE": "${ZANNI_STAGE}" }
    }
  }
}
```

A role is shared, so a secret in `mcp.json` must be a `${NAME}` reference, never a value. Each actor supplies its own value from its configuration's `credentials`, or from its environment. Two actors playing this role can then use different tokens. `zanni` rejects a literal value in an `env` or `headers` entry whose name looks like a secret.

### Tools and the workspace

A role that works on real files, such as a coder writing code and running its tests, or a writer revising a manuscript with a spell checker, asks for a **workspace**: Zanni's one built-in server.

```json
{
  "mcpServers": {
    "workspace": { "command": "zanni:workspace" }
  }
}
```

- **What it is:** a local folder on the actor's machine. At the start of each cue the actor fills it with every stage file the seat may read; the model works there with `workspace_read_file`, `workspace_write_file`, `workspace_list_files` and `workspace_run`; and when the cue ends done, the actor sends what changed back to the stage (D52).
- **What reaches the stage:** text files only, and none that the project's own `.gitignore` ignores, such as build output. Each change is an ordinary stage write, so the director checks it against the cue's paths, and a git stage commits it with the seat as author. A change outside the cue's paths is refused, and the refusal is in the report. A cue that fails, or stops at its budget, sends nothing.
- **What `run` may run:** only the commands the actor's configuration lists in `workspace.commands`, such as `[uv]` or `[npm, node]`; none by default. Running commands on a machine is its owner's decision, never the role's. The command's environment holds nothing that looks like a secret. A process a command leaves running, such as the app a tester starts and then probes, lasts until the cue ends, and no longer. A listed command runs with its owner's permissions, and the workspace isn't a sandbox: `uv run python` can do anything Python can, including writing outside the folder, so list only what you would let the role's model run on your machine.
- **Give it the project's files:** a role with a workspace usually reads the whole stage (`stage_read: ["/"]`), so the project's `.gitignore`, `pyproject.toml` or `package.json` reach the folder too.

**An actor brings its own tools,** as it brings its own models (D53). Its configuration may replace any server the role needs with one of its own, such as its favourite coding engine, and says what each call costs the play:

```yaml
# coder-1.yaml, an actor configuration
tools:
  workspace:
    command: some-engine            # stands for any MCP server that works in a folder
    args: [mcp, --folder, "${ZANNI_WORKSPACE}"]
    price: { per_call: 0 }          # what a play is charged per call: here, nothing
```

- **Only the tools the role needs:** a name the role's `needs.tools` doesn't list is refused.
- **`${ZANNI_WORKSPACE}`** is the workspace's folder; a server the actor brings also starts there. Its changes reach the stage the same way, at the end of the cue.
- **The price is the actor's word:** the director counts what the actor declares, as it counts models' costs. Under a budget, a tool with no price is refused at join, since an unknown cost is never counted as zero.

## 5. Publishing

A role lives in a git repository, at the root or in a folder of one. Tag each version `vX.Y.Z`; for a role in a subfolder, use `path/to/role/vX.Y.Z`. Plays refer to it as `host/owner/name@version`, such as `github.com/someone/tester@1.4.0`, and pin it to a commit in their `play.lock` ([versions](spec/role-package.md#versions)). A play can also use a local folder: `tester: roles/tester`.

## 6. Rehearse it

A rehearsal runs your role on cues, against a copy of a stage folder, with a director started for it on your machine (D29). It is the role's own test, and it ships with the package:

```
roles/slug-tester/
  rehearsals/
    smoke.yaml        # the cues and the checks
    smoke-stage/      # the starting state, copied fresh for every run
```

```yaml
# rehearsals/smoke.yaml
rehearsal: smoke
stage: ./smoke-stage
cues:
  - scene: Specify
    instructions: Read backlog/round-1.md and spec/slug.md. Write one pytest test for each acceptance criterion …
verify:
  - name: tests-pass
    command: [uv, run, --no-project, --with, pytest, python, -m, pytest, -q, tests]
```

To run it, point an actor configuration's `play` at the rehearsal, and run that configuration:

```yaml
# slug-tester.yaml, on your machine
name: slug-tester-1
role: ./roles/slug-tester
play: ./roles/slug-tester/rehearsals/smoke.yaml
models:
  - { provider: ollama, model: qwen3.8:27b, base_url: "${OLLAMA_BASE_URL}" }
```

```bash
uv run zanni slug-tester.yaml
```

- **Comparing models:** the same rehearsal, run with different `models`, is how to compare models on your role. [`docs/runs/milestone-2.md`](runs/milestone-2.md) shows one comparison.
- **Checking the folder:** `zanni <role folder>` also checks every rehearsal in `rehearsals/`.
- **On another machine:** `zanni rehearsals/smoke.yaml --serve --listen 0.0.0.0:8765` serves the rehearsal; an actor anywhere joins it by pointing its `play` at `http://<this machine>:8765`. Both sides need the same `ZANNI_JOIN_TOKEN` ([Getting started](getting-started.md#join-a-director-on-another-machine)).
- **Safety:** a rehearsal's `verify` commands run on your machine, so run rehearsals only from roles you trust. See the [rehearsal spec](spec/rehearsal.md).
