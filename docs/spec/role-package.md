# Role package

A role is a package anyone can write, version and publish: a local folder, a git repository, or a folder in one. A zanni is an empty shell until it is given a role. The role holds capabilities only; names, models and credentials belong to each actor's configuration (D14).

```
roles/tester/
  role.yaml       # Zanni's fields (this page)
  AGENTS.md       # character and instructions (standard)
  skills/         # skills in SKILL.md format (standard)
  mcp.json        # the MCP servers it expects, in the standard `mcpServers` format
  notes/          # curated lessons, private to the role
  rehearsals/     # the role's own tests: rehearsals and their stage folders (optional)
```

Only `role.yaml` is Zanni's own format. `AGENTS.md`, `skills/` and `mcp.json` follow their standards unchanged, and none of them may name a model vendor or an engine (golden rule 4). The repository's example is `examples/roles/tester/`.

## role.yaml

A role manifest is recognised by having `mission` (and no `parts`, which would make it a script).

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

A role's needs are **requests, not grants**. The script's part sets a ceiling on them, and the play grants them by casting the role. The enforcement column below says who holds the line.

### Fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `name` | text | yes | — | the director, at casting | The role's name. |
| `version` | `major.minor.patch` | yes | — | the director, when resolving references | The role's version. Write it as text: `1.4` without quotes is read as a number and rejected. |
| `mission` | text | yes | — | — (guidance to the model) | One sentence on what the role is for. |
| `model.needs.tools` | true or false | no | `false` | — (a hint for the actor configuration) | Whether the model must be able to call tools, natively or through the opt-in text format (D5). |
| `model.needs.context` | number, or with `k`/`m` (`32k`) | no | none | — (a hint for the actor configuration) | The smallest context window that works for this role. |
| `model.needs.tier` | text | no | none | — (a hint for the actor configuration) | The kind of model the role needs; see [Tiers](#tiers). |
| `model.suggested` | text | no | none | — (a hint) | A model the actor configuration may use. Roles never require a model (D11). |
| `needs.stage_read` | list of paths | no | none | the stage | Stage paths the role asks to read. A path ending in `/` is a folder ([Stage: paths](stage.md#paths)). |
| `needs.stage_write` | list of paths | no | none | the stage | Stage paths the role asks to write. |
| `needs.tools` | list of names | no | none | `zanni`, when validating the folder; the actor, at run time | The MCP servers the role needs. Each must be a server in the role's `mcp.json`. |
| `never` | list of text | no | none | — (guidance) | Things the role must never do. These are instructions to the model, **not limits**: the real limits are the stage's permissions and the verifiers. |
| `outputs` | map of path → description | no | none | `zanni`; verifiers, on the director's side | What the role produces. Each path must be inside `needs.stage_write`, and may hold a placeholder such as `<item>`. |

### Tiers

`model.needs.tier` is a free label, not a fixed list. Models change faster than a spec should. The tier tells whoever writes an actor's configuration what kind of model the role was written for, and nothing enforces it (D11). The reference roles use these labels:

| Tier | For |
|---|---|
| `judgement` | Deciding, designing and reviewing: the product owner, architect, designer and reviewers. |
| `coding` | Changing code through a coding engine: coders. |
| `basic` | Simple, repetitive steps where speed matters more than depth. |

## Versions

A remote role is referenced as `host/owner/repo@version`, or as `host/owner/repo/path/to/role@version` for a role in a subfolder of a repository. `version` is `major.minor.patch`.

It resolves to a git tag, tried in this order:

1. **For a role in a subfolder:** `path/to/role/vX.Y.Z`, the convention of repositories that hold several packages.
2. **`vX.Y.Z`.**
3. **`X.Y.Z`.**

The first tag that exists wins. If two of them exist and point to different commits, resolution fails, and the error names both tags. The play's lockfile then pins the commit, and the package's content hash ([Play: the lockfile](play.md#the-lockfile)).

Scripts are referenced and resolved the same way.

### Fetching

The director fetches a play's script and roles, and an actor fetches its role, with the `git` command (D37):

- **Where from:** `https://<host>/<owner>/<repo>.git`.
- **What:** only the tag's commit, shallow, without submodules. Fetching runs nothing: git never copies a repository's hooks.
- **The cache:** `~/.zanni/packages/<host>/<owner>/<repo>/<commit>/`. A package in a subfolder is that folder of the commit, and its content hash covers that folder only.
- **Offline once fetched:** a commit already in the cache is used without touching the network, once its hash is checked.
- **Authentication is git's:** Zanni passes no credentials. A private repository is reached with the person's own SSH keys or credential helper; `url.<base>.insteadOf` in their git config sends `https://` addresses through SSH. Git runs with `GIT_TERMINAL_PROMPT=0`, so a fetch that would ask for a password fails with a message instead of waiting.
- **Updating:** a play's packages stay at the commits in its `play.lock`. A tag that moved is refused; `zanni play.yaml --update` re-resolves them ([Play: the lockfile](play.md#the-lockfile)).

**Not in the first version:** version ranges, cleaning the cache, and checking signed tags (`TODO.md`).

## Checking a role

`zanni roles/tester/role.yaml` checks the manifest on its own. `zanni roles/tester`, passing the folder, also checks the rest of the package:

- **`role.yaml`:** as above, including that every output is inside `needs.stage_write`.
- **`AGENTS.md`:** present and not empty.
- **`skills/*/SKILL.md`:** every folder under `skills/` holds a `SKILL.md` whose frontmatter follows the [Agent Skills spec](https://agentskills.io/specification):
  - `name`: 1–64 lowercase letters, digits and single hyphens, not starting or ending with a hyphen, and matching its folder's name;
  - `description`: 1–1024 characters;
  - `license`, `compatibility` (up to 500 characters), `metadata` (text to text) and `allowed-tools`: optional.

  Fields the standard doesn't define are left alone, for other tools.
- **`mcp.json`:** the standard `mcpServers` shape:
  - every server has exactly one of `command` or `url`;
  - any `env` or `headers` value whose name looks like a secret must be a `${VAR}` reference, since a role is shared. The value comes from the actor's configuration (see [Actor configuration: credentials](actor-configuration.md#credentials)) or its environment.
  - Keys other MCP clients use, such as `type` or `disabled`, are left alone.
- **`needs.tools`:** every name is a server in `mcp.json`.
- **`rehearsals/*.yaml`:** every rehearsal is valid, and its stage folder exists ([Rehearsal](rehearsal.md)).

```
Role manifest: the role 'tester' 1.4.0.
  …
  folder: AGENTS.md; skills: explore-app, write-test; mcp.json servers: browser, test-runner
Valid.
```

## Not in the first version

- **A role-level budget:** the vision lists "budget" among a role's fields. A role asking for a budget raises questions the first version doesn't need to answer, such as how it combines with the play's budget, so for now the play's house rules alone set budgets.
- **Sandboxing roles from other people:** the first version runs only roles from machines and repositories the maintainer controls (the vision's first-version scope). Sandboxing comes with actors hosted by other people.
