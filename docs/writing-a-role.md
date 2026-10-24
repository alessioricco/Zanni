# Writing a role

A role is a package describing a persona: who it is, what it knows how to do, which tools it needs, and what it may touch. A zanni is an empty shell until it is given a role, so adding a role needs no code. A role holds capabilities only: names, models and credentials belong to each actor's configuration.

> **Status:** `zanni` validates a whole role folder today: `role.yaml`, `AGENTS.md`, the skills and `mcp.json`. Actors that load roles come with the engine adapter (D4 in [DECISIONS.md](../DECISIONS.md)), so you can start writing roles now.

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
name: tester
version: 1.4.0
mission: Turn acceptance criteria into tests; explore the running app and report findings.
model:
  needs: { tools: true, context: 32k, tier: judgement }
  suggested: claude-sonnet-5-5
needs:
  stage_read: [vision.md, backlog/, spec/]
  stage_write: [tests/, findings/]
  tools: [browser, test-runner]
never:
  - edit application code
outputs:
  findings/<item>.md: one finding per file, each with a failing test
```

- **`needs` are requests, not grants.** The play decides what to grant, and the stage enforces what a seat may read and write. A role can't give itself more access.
- **`never` is guidance for the model, not a limit.** The real limits are the stage's permissions and the verifiers. Write `never` rules anyway: they keep the role on task.
- **`model.needs` says what kind of model the role needs, not which one.** The model is chosen in each actor's configuration; `model.needs` and `suggested` are hints for whoever writes it. A role never requires a particular model or vendor.

- **`needs.tools` names the role's MCP servers,** and each must be a server in its `mcp.json`.
- **`outputs` must sit inside `needs.stage_write`.**
- **`model.needs.tier`** is a free label. The reference roles use `judgement`, `coding` and `basic`.

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

## 5. Publishing

A role lives in a git repository, at the root or in a folder of one. Tag each version `vX.Y.Z`; for a role in a subfolder, use `path/to/role/vX.Y.Z`. Plays refer to it as `host/owner/name@version`, such as `github.com/someone/tester@1.4.0`, and pin it to a commit in their `play.lock` ([versions](spec/role-package.md#versions)). A play can also use a local folder: `tester: roles/tester`.

## 6. Rehearse it

A rehearsal runs your role on cues, against a copy of a stage folder, with no director. It is the role's own test, and it ships with the package:

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
- **Safety:** a rehearsal's `verify` commands run on your machine, so run rehearsals only from roles you trust. See the [rehearsal spec](spec/rehearsal.md).
