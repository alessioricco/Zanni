# Zanni docs

Zanni is an open-source engine for teams of AI personas. Each process is a **zanni**, an empty shell that becomes an **actor** when given a **role**. A **script** is the reusable work; a **play** is one production of it, where a **director** casts actors into the script's parts and coordinates them on a shared **stage**, the play's workspace.

**Status: early.** `zanni <file>` validates Zanni files, runs an actor on its models, and lets it join a director over A2A. `zanni play.yaml` runs a whole play, on a folder, a git repository or an MCP stage server. See [what works today](getting-started.md#what-works-today), and the [roadmap](../ROADMAP.md).

## Using Zanni

| Page | Read it to |
|---|---|
| [Getting started](getting-started.md) | Install Zanni and check your first file |
| [Concepts](concepts.md) | Understand roles, actors, the director, the stage and plays, and how limits are enforced |
| [Zanni files](files.md) | Learn the kinds of file: actor configurations, plays, role manifests, scripts, lockfiles |
| [Writing a role](writing-a-role.md) | Build a role folder: `role.yaml`, `AGENTS.md`, skills, `mcp.json` |
| [Writing a script](writing-a-script.md) | Write the reusable work a play performs: parts, gates, acts and scenes |
| [Writing a stage server](writing-a-stage-server.md) | Keep a play's stage anywhere, behind an MCP server with five tools |
| [Models and keys](models-and-keys.md) | See where API keys go, and how local and cloud models will be chosen |
| [Command reference](cli.md) | Look up every option, output and exit code of `zanni` |
| [Troubleshooting](troubleshooting.md) | Fix the errors `zanni` reports |

## Working on Zanni

| Page | Read it to |
|---|---|
| [Contributing](contributing.md) | Set up the repository, follow the rules every change follows, and send a change |
| [Architecture](architecture.md) | Find your way around the codebase: what each module does and how a file flows through it |
| [Testing](testing.md) | Run the unit and conformance tests and CI, and add tests |
| [Coding agents and skills](agent-skills.md) | Work on Zanni with Claude Code or another agent, and download the shared skills |

## Reference

- [Spec](spec/README.md): the formats and protocol. The spec is the product; this codebase is its reference implementation.
- [Decisions](../DECISIONS.md): what was decided, why, and when to revisit it.
- [Spikes](spikes/): recorded experiments behind the decisions.
- [Recorded runs](runs/): what each milestone's runs showed, with models, versions, tokens and cost.
- [Roadmap](../ROADMAP.md): milestones, each with what "done" means.
