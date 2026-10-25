# Writing a stage server

A play's stage can live anywhere: a document store, a wiki, a ticket system, a bucket. With `stage: { backend: mcp, url: … }`, the stage is any MCP server that offers five tools (D47). This page is the contract such a server must meet. The spec's [stage page](spec/stage.md#mcp) is the full reference.

The repository's example, `examples/stage-servers/sqlite/server.py`, keeps the stage in a SQLite file. It uses only the official `mcp` SDK and the standard library, so you can copy it and replace its storage.

## What the server does, and what it doesn't

A stage server stores text files by path, and says what changed. That's all (D43):

- **It doesn't enforce permissions.** The director checks every seat's operation against that seat's permissions before it reaches your server. Your server sees only the director.
- **It never sees a seat or its token.** Seats reach the stage through the director's own MCP server, with their own short-lived tokens. Your server has one client, the director, with one token.
- **It doesn't decide anything with who wrote a file.** The director passes the seat and the cue with each write, as `author` and `note`, for your server to record if it wants to.

```
actor ──MCP, seat token──▶ the director's stage server ──▶ permission layer ──MCP, ZANNI_STAGE_TOKEN──▶ your server
```

## The five tools

Served over MCP's Streamable HTTP transport, at the URL the play names:

| Tool | Arguments | Returns |
|---|---|---|
| `stage_read` | `path` | the file's text |
| `stage_write` | `path`, `content`, and optionally `author`, `note` | the new change marker, as a string |
| `stage_list` | `path`, empty for the whole stage | the path of every file under it, at any depth, relative to the stage root |
| `stage_delete` | `path`, and optionally `author`, `note` | the new change marker |
| `stage_changes` | `since`, a change marker, or none for everything | `{ "changes": [{ "path": …, "change": "written" or "deleted" }], "marker": … }` |

- **Paths** are relative to the stage root, written with `/`, such as `notes/release-notes.md`. The director checks them before they reach you, but a server should still refuse a path that starts with `/`, contains `..` or `\`, or has an empty segment.
- **Writes** replace the whole file, and create it if it's missing. Folders are implied by paths: there is no separate "make a folder".
- **Text only.** Content is text. A server holding something else, such as an image, lists it and refuses to read it with `not-text`.
- **Change markers** are strings your server makes up, such as a counter or a version id. The director stores them and passes them back to `stage_changes`; it never reads meaning into them. Seats see the director's own markers, never yours.
- **`author` and `note`** are optional. The director sends the seat (such as `writer-1`) and the cue (such as `r1-c1: Scene 1: Draft`). Store them, or ignore them. If your tool's signature doesn't accept them, the director notices the error and stops sending them.
- **`stage_list`** is also how the director takes a snapshot of the stage for verifiers: it lists the whole stage, then reads every file.

## Errors

A refused operation is an MCP tool error whose text ends with `<code>: <message>`, in plain words:

| Code | When |
|---|---|
| `not-found` | `stage_read`, `stage_delete` or `stage_list` on a path that isn't there |
| `invalid-path` | a path your server can't store |
| `not-text` | `stage_read` on content that isn't text |
| `unknown-marker` | `stage_changes` with a marker your server never gave |
| `unavailable` | your server can't reach its own storage right now |

For example, in the SQLite server: `raise ToolError(f"not-found: {path} isn't on the stage")`. An MCP library may put its own words before the code; the director finds the code at the end.

The director treats any other failure, such as a refused connection or a timeout, as `unavailable`. It retries briefly and reconnects. If your server stays away, the director pauses the play, and the owner resumes it with `zanni gate <play> resume` once the server is back.

## The token

The director presents a bearer token on every request: `Authorization: Bearer <token>`. It comes from `ZANNI_STAGE_TOKEN` in the director's configuration's `credentials`. The play file names only the URL, never a secret.

Your server checks the token, and answers HTTP 401 to anything else. The SQLite server takes it from its own `ZANNI_STAGE_TOKEN` environment variable, and compares it with `secrets.compare_digest`. A server that runs anywhere but `127.0.0.1` should sit behind TLS, so the token doesn't cross the network in the clear.

## Changes made elsewhere

The director keeps its own record of the play's writes, and seats see that record. If someone edits the stage through another route while a play runs, such as a person in the wiki's own editor, seats won't see that in `changes`. They will see it in `stage_read` and `stage_list`.

## Try it

Start the example server, seeded with a folder:

```bash
export ZANNI_STAGE_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
uv run python examples/stage-servers/sqlite/server.py --db /tmp/stage.db --listen 127.0.0.1:8800 \
  --seed examples/plays/release-notes/stage
```

```
Seeded the stage with 3 file(s) from examples/plays/release-notes/stage
Serving the stage in /tmp/stage.db at http://127.0.0.1:8800/mcp
```

Then run a play on it: [getting started](getting-started.md#a-play-on-a-stage-server).

- **`zanni --check play.yaml`** only checks the play file. The director first reaches your server when the play starts: it calls `stage_changes` once to check the token, then checks that the stage holds what the script's `stage.expects` lists. Either failing stops the play before it starts, with exit code 2.
- **Testing your own server:** `tests/test_stage_backends.py` runs the same tests on every backend, the example server included. To run them against yours, add an entry to its `BACKENDS`, like its `mcp` one. That entry starts the server seeded with the test files (`SEED`), and yields `Stage(McpBackend(url, token))`.
