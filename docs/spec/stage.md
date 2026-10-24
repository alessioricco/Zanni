# Stage

The stage is a play's workspace: the shared state the actors work on, such as a vision, a backlog, tests and code, or the chapters of a book. What it is made of depends on the play: a folder, a git repository, or any store behind an MCP server. The spec defines what every stage offers and how its permissions are enforced, independently of the backend that stores it (D12, D43).

## Paths

- **Location:** every stage item is addressed by a path relative to the stage's root, written with `/`, such as `backlog/round-1.md`.
- **Rejected paths:** absolute paths, `..` segments, empty segments and backslashes are rejected with `invalid-path`.
- **Folder rules:** a path rule ending in `/` means a folder and everything under it. A rule without it means exactly that file. `backlog/` covers `backlog/round-1.md`; `vision.md` covers only `vision.md`.
- **The whole stage:** the rule `/` alone covers everything on the stage. It is a rule, not a path: stage paths still never start with `/`.

## Operations

Every backend offers the same five operations to every seat:

| Operation | Inputs | Output | Errors |
|---|---|---|---|
| `read` | `path` | the file's content | `invalid-path`, `not-permitted`, `not-found` |
| `write` | `path`, `content` | the new change marker | `invalid-path`, `not-permitted` |
| `list` | `path` (a folder; empty for the root) | the files and folders under it that the seat may read | `invalid-path`, `not-found` |
| `delete` | `path` | the new change marker | `invalid-path`, `not-permitted`, `not-found` |
| `changes` | `since` (a change marker, or none for everything) | each changed path since then, with `written` or `deleted`, and the current change marker | `unknown-marker` |

- **Text only:** content is text. A backend holding a file that isn't text, such as an image in a repository, lists it, and refuses to `read` it with `not-text`.

- **Change markers:** a change marker is an opaque string. Seats store it and pass it back to `changes`; they never interpret it.
- **Writes:** `write` creates any missing folders, and replaces the file if it exists.
- **Errors:** every error carries a plain-words message saying what was refused and why. `not-permitted` names the seat's rule that applied. Any operation may return `unavailable`, when the backend can't be reached.
- **Shared writes:** a write is on the stage for every seat at once, in the order the director receives it. There are no per-seat workspaces and no merges; when two seats may write the same path, the last write wins (D44).

## Permissions

Each seat gets two lists of path rules: what it may read and what it may write. They are worked out when the director casts the seat:

1. **The role asks:** `needs.stage_read` and `needs.stage_write` in its `role.yaml`.
2. **The script's part sets the ceiling:** `reads` and `writes` in the part, when the script gives them. A seat may write only paths inside both what its role asks for and its part's `writes`. Reading works the same way with `reads`.
3. **The play grants it:** by casting that role into that part. In the first version, a play can't widen or narrow the result.

- **Writing implies reading:** a seat may always read the paths it may write.
- **Enforcement:** the director enforces both lists on every operation, in one layer above every backend (D43, golden rule 5). Nothing depends on the actor, or on the backend, respecting them.

## Transport: how actors reach the stage

Decided at ask point A (D16).

### Every backend: the stage as an MCP server

The director serves the stage as an MCP server. Its tools are the five operations: `stage_read`, `stage_write`, `stage_list`, `stage_delete` and `stage_changes`.

- **At casting:** each seat receives the server's address and credentials scoped to that seat.
- **On every call:** the server identifies the seat from its credentials and applies its permissions.
- **At release:** the director revokes those credentials.

Actors need nothing but MCP, which is how they reach every other tool.

The server, as served by Zanni's director (D31):

- **Transport and address:** Streamable HTTP, at the cast's `stage.mcp_url`. Zanni's director serves it at `/stage/mcp` under its own address.
- **Credentials:** the seat's `stage.token`, as an HTTP bearer token on every request. A missing, unknown, expired or revoked token gets HTTP 401.
- **The tools:**

  | Tool | Arguments | Result |
  |---|---|---|
  | `stage_read` | `path` | The file's text. |
  | `stage_write` | `path`, `content` | The new change marker. |
  | `stage_list` | `path` (optional; the root when empty) | The files under it that the seat may read. |
  | `stage_delete` | `path` | The new change marker. |
  | `stage_changes` | `since` (optional) | `{ changes: [{ path, change }], marker }`, with only the paths the seat may read. |

- **Errors:** a refused operation is a tool result with `isError` set, whose text ends with `<code>: <message>`, using the errors of the [operations](#operations), such as `not-permitted: this seat may not write app/x.py; it may write: tests/`. An MCP server library may put its own words before it.

### Direct access, for a checkout

Coding engines work on a real checkout. Giving a seat direct access to a git stage, a clone it pushes from, is planned with the coding engine in milestone 6 (D46): `zanni.cast`'s `stage.direct` is reserved for it, and no director sends it yet. Every seat uses MCP only.

## Backends

A backend stores the stage's files, and nothing else (D43). The director puts one layer above every backend, which checks paths, enforces each seat's permissions, revokes seats, and keeps the record of who changed what; the backend never sees a seat or its token.

```
actor ──MCP, seat token──▶ the director's stage server
                              ▼
                     permission layer, and the record of changes   (the director)
                              ▼
                   backend: folder | git | mcp                     (storage)
```

A backend must:

- store, read, list and delete text files by stage path, and say what changed;
- give the director a **snapshot**: the whole stage as a real folder, for verifiers (D45);
- keep a write once it has answered it: a seat lost mid-cue loses nothing already written.

- **Change markers:** the director's record gives the markers seats see, positions in its list of changes, so they mean the same on every backend. The backend's own marker (a commit hash, a server's marker) is kept beside each entry.
- **Who wrote what:** the director passes each write's seat and cue to the backend as labels. A backend may store them, as git does in its commits; it never decides with them.

The first version specifies three backends.

### `folder`

The stage is a folder on the director's machine. This suits plays whose work is documents, and runs every example of the first version.

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `backend` | `folder` | yes | — | |
| `path` | text | yes | — | The folder, relative to the play file or absolute. |

- **Snapshot:** a copy of the folder.

### `git`

The stage is a git repository. This suits plays whose work is code (D46).

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `backend` | `git` | yes | — | |
| `url` | text | yes | — | The repository: any git remote, or a local path. |
| `branch` | text | no | `main` | The branch each run starts from. A run never commits to it. |
| `push` | `approved` or `always` | no | `approved` | When the director pushes the run's branch ([below](#pushing)). |

- **The clone:** the director clones `url` into `log/<run-id>-stage/` in the play's folder, and makes a branch `zanni/<play>/<run-id>` from the tip of `branch`. A clone that fails stops the play before it starts.
- **Writes:** each `write` and `delete` is a commit on the run's branch, with the seat as author (`<seat> <<seat>@zanni.invalid>`), the director as committer, and the cue as its message.
- **What it shows:** paths under `.git/` are `invalid-path`. Files that aren't text are listed, and refused on `read` with `not-text`. A write to a path `.gitignore` ignores is refused with `invalid-path`, because it would never be committed.
- **Snapshot:** the run's branch at its latest commit, extracted into a fresh folder.
- **Credentials:** git's own on the director's machine, such as an SSH agent or a credential helper. Git never prompts (`GIT_TERMINAL_PROMPT=0`, SSH `BatchMode`), and Zanni stores no git credential. Seats never touch git.

#### Pushing

The director pushes the run's branch, and only it, to `url`:

| `push` | At each approved gate | At the end, when the play is done | At the end of an unfinished run |
|---|---|---|---|
| `approved` | yes | yes | no: the run's work stays in `log/<run-id>-stage/`, and the director prints the `git push` command that publishes it |
| `always` | yes | yes | yes |

A push that fails stops nothing: it is logged (`push`) and printed, and the work stays in the run's folder. Merging the run's branch into `branch` is a person's decision, outside Zanni, as with a pull request.

### `mcp`

The stage is any MCP server that offers the five operations as tools: a document store, a wiki, a ticket system, a bucket (D47). It is the extension point for kinds of stage Zanni doesn't ship.

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `backend` | `mcp` | yes | — | |
| `url` | `http` or `https` URL | yes | — | The server's Streamable HTTP endpoint. |

- **The contract:** the same tools the director serves to its seats ([above](#every-backend-the-stage-as-an-mcp-server)), with two optional arguments on `stage_write` and `stage_delete`: `author`, the seat, and `note`, the cue. A server may record them, or ignore them. A refused operation is a tool error whose text ends with `<code>: <message>`. The server doesn't enforce seats' permissions: the director does.
- **Credentials:** the director presents `ZANNI_STAGE_TOKEN`, from its own configuration's `credentials`, as `Authorization: Bearer <token>`. The play file holds no secret. Seats never see the token.
- **Unreachable:** an operation that gets `unavailable` is retried briefly. If the server stays away, the play pauses as when every director model fails, until the owner resumes it ([Play: gates and pauses](play.md#gates-and-pauses)).
- **Snapshot:** every file, listed and read into a fresh folder.
- **Changes made elsewhere:** the director's record holds the play's own writes. Changes someone else makes on the server don't appear in `changes`.
- **An example:** `examples/stage-servers/sqlite/`, a stage server keeping documents in SQLite ([Writing a stage server](../writing-a-stage-server.md)).

## In the play file

The play's `stage` field picks the backend:

```yaml
stage: git@github.com:alessio/habit-tracker.git               # shorthand: a git URL or a .git path means git
stage: ./chapters                                             # shorthand: anything else is a local folder
stage: { backend: git, url: https://github.com/a/b.git, branch: dev, push: always }
stage: { backend: folder, path: ./chapters }
stage: { backend: mcp, url: http://docs.internal:8800/mcp }      # no shorthand: the backend is named
```

- **Git shorthand:** a string is a git URL if it looks like `git@host:path`, a `ssh://`, `git://`, `http://` or `https://` URL ending in `.git`, or any path ending in `.git`.
- **Fields must match the backend:** a git stage takes `url`, `branch` and `push`; a folder stage takes `path`; an `mcp` stage takes `url`, an `http` or `https` URL. Any other combination is an error.

## Not in this spec yet

- **Direct access** to a git stage, for coding engines: milestone 6 (D46).
- **Isolated writes,** a workspace per seat merged by the director (D44), and **binary content** (D43): `TODO.md`.
- **Narrowing:** narrowing a seat's permissions from the play is not in the first version.
