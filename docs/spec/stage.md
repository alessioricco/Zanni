# Stage

The stage is a play's workspace: the shared state the actors work on, such as a vision, a backlog, tests and code, or the chapters of a book. What it is made of depends on the play. The spec defines what every stage offers and how it enforces permissions, independently of the backend that stores it (D12).

## Paths

- **Location:** every stage item is addressed by a path relative to the stage's root, written with `/`, such as `backlog/round-1.md`.
- **Rejected paths:** absolute paths, `..` segments, empty segments and backslashes are rejected with `invalid-path`.
- **Folder rules:** a path rule ending in `/` means a folder and everything under it. A rule without it means exactly that file. `backlog/` covers `backlog/round-1.md`; `vision.md` covers only `vision.md`.

## Operations

Every backend offers the same five operations to every seat:

| Operation | Inputs | Output | Errors |
|---|---|---|---|
| `read` | `path` | the file's content | `invalid-path`, `not-permitted`, `not-found` |
| `write` | `path`, `content` | the new change marker | `invalid-path`, `not-permitted` |
| `list` | `path` (a folder; empty for the root) | the files and folders under it that the seat may read | `invalid-path`, `not-found` |
| `delete` | `path` | the new change marker | `invalid-path`, `not-permitted`, `not-found` |
| `changes` | `since` (a change marker, or none for everything) | each changed path since then, with `written` or `deleted`, and the current change marker | `unknown-marker` |

- **Change markers:** a change marker is an opaque string. Seats store it and pass it back to `changes`; they never interpret it.
- **Writes:** `write` creates any missing folders, and replaces the file if it exists.
- **Errors:** every error carries a plain-words message saying what was refused and why. `not-permitted` names the seat's rule that applied. A backend may also return `unavailable` from any operation, when it can't be reached.

## Permissions

Each seat gets two lists of path rules: what it may read and what it may write. They are worked out when the director casts the seat:

1. **The role asks:** `needs.stage_read` and `needs.stage_write` in its `role.yaml`.
2. **The script's part sets the ceiling:** `reads` and `writes` in the part, when the script gives them. A seat may write only paths inside both what its role asks for and its part's `writes`. Reading works the same way with `reads`.
3. **The play grants it:** by casting that role into that part. In the first version, a play can't widen or narrow the result.

- **Writing implies reading:** a seat may always read the paths it may write.
- **Enforcement:** the stage enforces both lists on every operation (golden rule 5). Nothing depends on the actor respecting them.

## Transport: how actors reach the stage

Decided at ask point A (D16).

### Every backend: the stage as an MCP server

The director serves the stage as an MCP server. Its tools are the five operations: `stage_read`, `stage_write`, `stage_list`, `stage_delete` and `stage_changes`.

- **At casting:** each seat receives the server's address and credentials scoped to that seat.
- **On every call:** the server identifies the seat from its credentials and applies its permissions.
- **At release:** the director revokes those credentials.

Actors need nothing but MCP, which is how they reach every other tool.

### Git backends: direct access for a checkout

Coding engines work on a real checkout, so a `git` stage may also give a seat direct access to the repository:

- **Branch:** the seat clones the repository and pushes only to its own branch, `zanni/<play>/<seat>`.
- **Merging:** before merging a seat's branch, the director checks every path changed by its commits against the seat's write permissions. A branch that touches any path outside them isn't merged, and the refusal is logged.
- **Who gets it:** a clone holds the whole repository, so direct access is offered only to seats whose read permissions cover the whole stage. Every other seat uses MCP only. This keeps read permissions enforceable.

## Backends

A backend must:

- implement the five operations with the errors above;
- enforce each seat's permissions;
- produce change markers that `changes` accepts;
- keep a seat's writes from being lost when the actor stops answering. The work survives on the stage.

The first version specifies two backends.

### `git`

The stage is a git repository. This suits plays whose work is code.

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `backend` | `git` | yes | — | |
| `url` | text | yes | — | The repository. |
| `branch` | text | no | `main` | The branch seats start from, and that the director merges into. |

- **Branches:** each seat works on its own branch, `zanni/<play>/<seat>`. Through MCP, `write` and `delete` become commits on that branch.
- **Merging:** the director merges seats' branches into `branch` when the script says to, such as at the end of a scene. A merge conflict is reported to the director, which decides who resolves it as the script describes.
- **Change markers:** commit hashes on `branch`.

### `folder`

The stage is a folder on the director's machine, managed by the director. This suits plays whose work is documents, and proves that the stage doesn't depend on git.

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `backend` | `folder` | yes | — | |
| `path` | text | yes | — | The folder, relative to the play file or absolute. |

- **Access:** only through MCP. There is no direct access.
- **Changes:** the director keeps an append-only record of every write and delete; change markers are positions in it.
- **Ordering:** writes are applied in the order the director receives them. There are no branches.

## In the play file

The play's `stage` field picks the backend:

```yaml
stage: git@github.com:alessio/habit-tracker.git               # shorthand: a git URL or a .git path means git
stage: ./chapters                                             # shorthand: anything else is a local folder
stage: { backend: git, url: https://github.com/a/b.git, branch: dev }
stage: { backend: folder, path: ./chapters }
```

- **Git shorthand:** a string is a git URL if it looks like `git@host:path`, a `ssh://`, `git://`, `http://` or `https://` URL ending in `.git`, or any path ending in `.git`.
- **Fields must match the backend:** a git stage takes `url` and `branch`, and a folder stage takes `path`. Any other combination is an error.

## Not in this spec yet

- **Run time:** the operations' behaviour at run time, and the MCP tool schemas in detail, come with milestone 5 ("Stage backends").
- **Narrowing:** narrowing a seat's permissions from the play is not in the first version.
