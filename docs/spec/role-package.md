# Role package

A role is a package anyone can write, version and publish: a local folder, a git repository, or a folder online. It holds capabilities only; names, models and credentials belong to each actor's configuration (D14).

```
roles/tester/
  role.yaml       # Zanni's fields (this page)
  AGENTS.md       # character and instructions (standard)
  skills/         # skills in SKILL.md format (standard)
  mcp.json        # MCP servers it expects, standard `mcpServers` format
  notes/          # curated lessons, private to the role
```

Only `role.yaml` is Zanni's own format. `AGENTS.md`, `skills/` and `mcp.json` follow their standards unchanged, and none of them may name a model vendor or an engine (golden rule 4).

## role.yaml

A role manifest is recognised by having `mission`. `zanni role.yaml` validates it.

```yaml
name: tester
version: 1.4.0
mission: Turn acceptance criteria into tests; explore the running app and report findings.
model: { needs: { tools: true, tier: judgement }, suggested: claude-sonnet-5-5 }
needs:
  stage_read: [vision.md, backlog/, spec/]
  stage_write: [tests/, findings/]
  tools: [browser, test-runner]
never:
  - edit application code
  - change priorities
outputs:
  findings/<item>.md: one finding per file, each with a failing test
```

A role's needs are **requests, not grants**. The play grants them or not, and the enforcement column below says who holds the line.

### Fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `name` | text | yes | — | the director, at casting | The role's name. |
| `version` | `major.minor.patch` | yes | — | the director, at casting | The role's version. Write it as text: `1.4` without quotes is read as a number and rejected. |
| `mission` | text | yes | — | — (guidance to the model) | One sentence on what the role is for. |
| `model.needs.tools` | true or false | no | `false` | — (a hint for the actor configuration) | Whether the model must be able to call tools, natively or through the opt-in text format (D5). |
| `model.needs.context` | number, or with `k`/`m` (`32k`) | no | none | — (a hint for the actor configuration) | The smallest context window that works for this role. |
| `model.needs.tier` | text | no | none | — (a hint for the actor configuration) | The kind of model the role needs, such as `judgement`. **Draft:** the list of tiers isn't fixed. |
| `model.suggested` | text | no | none | — (a hint) | A model the actor configuration may use. Roles never require a model (D11). |
| `needs.stage_read` | list of paths | no | none | the stage | Stage paths the role asks to read. A path ending in `/` is a folder. |
| `needs.stage_write` | list of paths | no | none | the stage | Stage paths the role asks to write. |
| `needs.tools` | list of text | no | none | the actor, under the play's grants | Kinds of tool the role asks for. **Draft:** how these names map to the servers in `mcp.json`. |
| `never` | list of text | no | none | — (guidance) | Things the role must never do. These are instructions to the model, **not limits**. The real limits are stage permissions and verifiers. |
| `outputs` | map of path → description | no | none | verifiers, on the director's side | What the role produces. **Draft:** how verifiers check outputs. |

## Draft

- **Budget:** a role-level budget request (the vision lists "budget" among a role's Zanni fields) isn't specified yet.
- **Publishing:** how a version maps to a commit, and the `roles.lock` format, aren't specified yet.
- **Sandboxing:** how roles from other people are sandboxed isn't specified yet.
