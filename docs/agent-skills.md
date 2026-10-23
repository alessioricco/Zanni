# Coding agents and skills

Zanni is built with coding agents as well as by hand. Everything an agent needs to work on the repository is in the repository, so people and agents follow the same rules.

## Instructions for agents

- **[`AGENTS.md`](../AGENTS.md):** the instructions for any coding agent: what Zanni is, the vocabulary, the golden rules, limits for agent sessions, the stack and the commands. It follows the [AGENTS.md](https://agents.md) convention, which most coding agents read.
- **`CLAUDE.md`:** imports `AGENTS.md` (`@AGENTS.md`), so Claude Code reads the same instructions. Edit `AGENTS.md`, never `CLAUDE.md`.

The limits for agent sessions in `AGENTS.md` apply to every agent:

- never tag, push or publish;
- never handle API keys;
- one commit per numbered item of a prompt;
- stop and ask on any decision the prompt doesn't cover.

## Shared skills

[`SKILLS.md`](../SKILLS.md) lists the skills, from Anthropic's official repository ([anthropics/skills](https://github.com/anthropics/skills)), that agents use on this project, and says why each is needed:

| Skill | Used for |
|---|---|
| `mcp-builder` | Designing MCP servers and their tools, such as Zanni's verifiers |
| `skill-creator` | Writing role skills in the SKILL.md format, and testing when they trigger |
| `webapp-testing` | Driving a running web app with Playwright, for the software play's tester and browser verifiers |

The skills aren't committed. Download them with:

```bash
scripts/get-skills.sh
```

- **What it does:** it downloads each listed skill, at the commit pinned in `SKILLS.md`, into `.claude/skills/`, where Claude Code finds a project's skills. Start a new Claude Code session afterwards to pick them up.
- **Other agents:** for an agent that looks elsewhere, pass the folder:

  ```bash
  scripts/get-skills.sh --dir .agents/skills
  ```

- **Requirements:** the script needs only `curl` and `tar`, and runs on macOS's bash 3.2 as well as on Linux.
- **Re-running:** it is safe to re-run. Each listed skill is replaced with the pinned version, and if any listed name doesn't exist, nothing is changed.
- **Git:** each downloaded folder gets its own `.gitignore`, so downloads stay out of git, while any skill the project writes itself in `.claude/skills/` is committed as usual.
- **Extras:** `webapp-testing`'s scripts need Playwright (`pip install playwright && playwright install chromium`), and `skill-creator`'s eval scripts need Python. Zanni itself depends on neither.

### Changing the list or updating the skills

Edit the `skills` block at the end of `SKILLS.md`:

```skills
repo: anthropics/skills
commit: <full 40-character commit SHA>
dir: .claude/skills
mcp-builder
skill-creator
webapp-testing
```

1. Add or remove a name, or set `commit` to a newer commit to update.
2. Re-run the script.
3. Commit `SKILLS.md`, updating the table and the reason for each skill.

The script reads this block, so it is the only list.

## Prompts

Larger changes are often written first as a prompt for a coding agent. A prompt has numbered items, one commit each, and the docs update is one of the items. It ends with a report of what ran.

Reports claim only what ran in that session, and name the exact models and versions used.
