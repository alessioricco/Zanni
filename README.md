# Zanni

An open-source engine for teams of AI personas. Each process is a **zanni**, an empty shell that becomes an **actor** when given a **role**. A **script** is the reusable work; a **play** is one production of it, where a **director** casts actors into the script's parts and coordinates them on a shared **stage**, the play's workspace.

- **Roles and scripts are packages, not code.** A role (`role.yaml`, `AGENTS.md`, skills, `mcp.json`) and a script can be written and published by anyone, and the same script can be staged by many companies.
- **Actors run anywhere.** They can run on a laptop, a GPU workstation or a cloud server, each with its own configuration: its models, local or cloud, and its credentials.
- **Limits can't be bypassed.** Whoever runs the play sets them, and no role can loosen them.
- **Verifiers decide when work is done**, not the actor that did it.
- **Built on standards:** AGENTS.md, Agent Skills, MCP and A2A. Zanni specifies only the gaps, and [the spec](docs/spec/README.md) is the product.

**Status: early development.** `zanni <file>` validates Zanni files and runs them. An actor runs on its models and joins a director over A2A, and `zanni play.yaml` starts a director that runs a whole play: it casts local seats and actors joining from other machines, follows the script, runs its verifiers, and enforces the budget and the human gates ([getting started](docs/getting-started.md#running-a-play)). The stage is a folder, a git repository, or any MCP stage server ([getting started](docs/getting-started.md#a-play-on-a-git-stage)); see the [roadmap](ROADMAP.md) for what comes next.

## Quick start

```bash
git clone https://github.com/alessioricco/Zanni.git && cd Zanni
uv sync
uv run zanni --check examples/plays/habit-tracker/play.yaml   # validate a play, and show what it would run
```

## Documentation

**Using Zanni**
- [Getting started](docs/getting-started.md)
- [Concepts](docs/concepts.md)
- [Zanni files](docs/files.md)
- [Writing a role](docs/writing-a-role.md)
- [Writing a script](docs/writing-a-script.md)
- [Writing a stage server](docs/writing-a-stage-server.md)
- [Models and keys](docs/models-and-keys.md)
- [Command reference](docs/cli.md)
- [Troubleshooting](docs/troubleshooting.md)

**Working on Zanni**
- [Contributing](docs/contributing.md)
- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
- [Coding agents and skills](docs/agent-skills.md): `scripts/get-skills.sh` downloads the shared agent skills.

**Reference**
- [Spec](docs/spec/README.md)
- [Decisions](DECISIONS.md)
- [Roadmap](ROADMAP.md)
- [All docs](docs/README.md)

## Licence

MIT. See [LICENSE](LICENSE).
