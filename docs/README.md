# Zanni docs

Zanni is an open-source engine for teams of AI personas. Each **actor** plays a **role** defined in a folder. A **director** casts the actors and coordinates them on a shared **stage**, following a **play**.

**Status: early.** `zanni <file>` validates Zanni files and shows what it would run, but nothing runs actors or models yet. The [roadmap](../ROADMAP.md) says what comes next.

## Using Zanni

| Page | Read it to |
|---|---|
| [Getting started](getting-started.md) | Install Zanni and check your first file |
| [Concepts](concepts.md) | Understand roles, actors, the director, the stage and plays, and how limits are enforced |
| [Zanni files](files.md) | Learn the three kinds of file: actor files, play files, role manifests |
| [Writing a role](writing-a-role.md) | Build a role folder: `role.yaml`, `AGENTS.md`, skills, `mcp.json` |
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
- [Roadmap](../ROADMAP.md): milestones, each with what "done" means.
