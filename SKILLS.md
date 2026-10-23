# Agent skills for working on Zanni

These are skills from Anthropic's official repository ([anthropics/skills](https://github.com/anthropics/skills)) that coding agents use when working on this repository.

**Getting them:** run `scripts/get-skills.sh`. The skills are not committed to this repository. The script downloads them, at the commit pinned below, into `.claude/skills/`, which is where Claude Code looks for a project's skills. Each downloaded folder gets its own `.gitignore`, so the downloads stay out of git, while skills this project writes itself in `.claude/skills/` are committed as usual.

Other agents may look for skills in another folder; pass it with `--dir`, for example `scripts/get-skills.sh --dir .agents/skills`.

| Skill | Why Zanni needs it | Source |
|---|---|---|
| `mcp-builder` | Zanni has no built-in tools. Everything an actor can do comes from an MCP server, and Zanni ships some of its own, such as verifiers. This skill covers designing MCP servers and their tools. | [skills/mcp-builder](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/mcp-builder) |
| `skill-creator` | Every Zanni role ships skills in the SKILL.md format, so writing them and measuring whether they trigger is core work for the roles, and for the reference roles of the first play. | [skills/skill-creator](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/skill-creator) |
| `webapp-testing` | The software play's tester explores the running app, and its verifiers run browser tests on it. This skill covers driving a local web app with Playwright. | [skills/webapp-testing](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/webapp-testing) |

All three are licensed under Apache 2.0. Each folder includes its `LICENSE.txt`.

**Requirements:**

- **The script:** `curl` and `tar` only.
- **`webapp-testing`:** its scripts also need Python with Playwright (`pip install playwright && playwright install chromium`). Zanni doesn't depend on Playwright.
- **`skill-creator`:** its eval scripts need Python. They are not part of Zanni's test suite.

## Also relevant, but not a skill

- **[Agent Skills specification](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/spec/agent-skills-spec.md)** (and [agentskills.io](https://agentskills.io)): the SKILL.md format that Zanni roles use (D4). It is referenced from the role package spec, not downloaded.

## Not included, and why

- **`claude-api`:** Claude Code has it built in. Zanni reaches models through Pydantic AI, not the Anthropic SDK directly.
- **`docx`, `pdf`, `pptx`, `xlsx`, `doc-coauthoring`, `internal-comms`:** Zanni's docs are Markdown in this repository, written under the working agreements.
- **`algorithmic-art`, `canvas-design`, `frontend-design`, `brand-guidelines`, `theme-factory`, `slack-gif-creator`, `web-artifacts-builder`:** Zanni has no visual design work in its first version. The web interface is out of scope.
- **`academy-guide`, `discernment-nudge`:** these aren't related to building Zanni.

## Changing the list

1. Edit the block below.
2. To update the skills, set `commit` to a newer commit of the repository.
3. Re-run the script.
4. Commit this file. The block is what the script reads.

```skills
repo: anthropics/skills
commit: dbd4588f9e1033efb41dad4bef2f7947c8993d44
dir: .claude/skills
mcp-builder
skill-creator
webapp-testing
```
