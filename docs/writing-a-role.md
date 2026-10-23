# Writing a role

A role is a folder describing a persona: who it is, what it knows how to do, which tools it needs, and what it may touch. The same engine plays any role, so adding a role needs no code.

> **Status:** today `zanni` validates `role.yaml`, and checks nothing else in the folder. The rest of this page is the format roles will be loaded from (D4 in [DECISIONS.md](../DECISIONS.md)), so you can start writing roles now.

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
- **`model.needs` says what kind of model the role needs, not which one.** The actor's host picks a model that matches. `suggested` is only a hint: a role never requires a particular model or vendor.

Check it:

```bash
uv run zanni roles/tester/role.yaml
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

Each skill is a folder with a `SKILL.md`, in the [Agent Skills](https://agentskills.io) format: YAML frontmatter with `name` and `description`, then the instructions.

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

`${VAR}` is expanded from the environment, so no secret ever goes in the file.

## 5. Publishing

A role lives in a git repository, at the root or in a folder of one. Plays refer to it as `host/owner/name@version`, such as `github.com/someone/tester@1.4.0`, and pin it to a commit in their `roles.lock`.

**Draft:** how a version resolves to a commit, and the `roles.lock` format, aren't specified yet; see the [role package spec](spec/role-package.md#draft). For now, a play can use a local folder: `tester: roles/tester`.
