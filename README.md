# Zanni

An open-source engine for teams of AI personas. Each **actor** plays a **role** defined in a folder. A **director** casts actors and coordinates them on a shared **stage**, following a **play**.

- **Roles are configuration, not code.** A role is a folder (`role.yaml`, `AGENTS.md`, skills, `mcp.json`) that anyone can write and publish.
- **Actors run anywhere.** They can run on a laptop, a GPU workstation or a cloud server, each with its own model, local or cloud.
- **Limits can't be bypassed.** Whoever runs the play sets them, and no role can loosen them.
- **Verifiers decide when work is done**, not the actor that did it.
- **Built on standards:** AGENTS.md, Agent Skills, MCP and A2A. Zanni specifies only the gaps, and [the spec](docs/spec/README.md) is the product.

**Status: early development.** `zanni <file>` validates Zanni files and shows what it would run. Nothing runs actors yet; see the [roadmap](ROADMAP.md).

## Quick start

```bash
git clone https://github.com/alessioricco/zanni.git && cd zanni
uv sync
uv run zanni examples/plays/habit-tracker/play.yaml
```

## Documentation

**Using Zanni**
- [Getting started](docs/getting-started.md)
- [Concepts](docs/concepts.md)
- [Zanni files](docs/files.md)
- [Writing a role](docs/writing-a-role.md)
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
