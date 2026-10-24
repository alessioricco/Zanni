"""An example stage server (D47): a play's stage kept in SQLite, served over MCP with a bearer token.

Any MCP server offering these five tools can be a Zanni stage. This one uses only the official `mcp` SDK and the
standard library, so it can be copied as a starting point for a stage kept anywhere else: a wiki, a ticket system,
a bucket. It stores and retrieves; it doesn't enforce anyone's permissions, because the director does that for every
seat, above whatever stores the stage (D43).

    ZANNI_STAGE_TOKEN=… python server.py --db notes.db --listen 127.0.0.1:8800 [--seed ./folder]

The director reaches it at http://127.0.0.1:8800/mcp, with the same ZANNI_STAGE_TOKEN in its configuration.
"""

import argparse
import os
import re
import secrets
import sqlite3
import sys
from pathlib import Path

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

SCHEMA = """
create table if not exists files (path text primary key, content text not null, author text, note text);
create table if not exists changes (id integer primary key autoincrement, path text not null, change text not null,
                                    author text, note text);
"""
BAD_PATH = re.compile(r"(^/|\\|(^|/)\.{1,2}(/|$)|//)")


class Store:
    """Files and an append-only list of changes; a change marker is the id of the latest change."""

    def __init__(self, db: Path):
        self.db = sqlite3.connect(db, check_same_thread=False, isolation_level=None)
        self.db.executescript(SCHEMA)

    def marker(self) -> str:
        return str(self.db.execute("select coalesce(max(id), 0) from changes").fetchone()[0])

    def read(self, path: str) -> str:
        row = self.db.execute("select content from files where path = ?", (path,)).fetchone()
        if row is None:
            raise ToolError(f"not-found: {path} isn't on the stage")
        return row[0]

    def write(self, path: str, content: str, author: str | None, note: str | None) -> str:
        with self.db:
            self.db.execute("insert into files values (?, ?, ?, ?) on conflict(path) do update set content = "
                            "excluded.content, author = excluded.author, note = excluded.note",
                            (path, content, author, note))
            self.db.execute("insert into changes (path, change, author, note) values (?, 'written', ?, ?)",
                            (path, author, note))
        return self.marker()

    def delete(self, path: str, author: str | None, note: str | None) -> str:
        with self.db:
            if self.db.execute("delete from files where path = ?", (path,)).rowcount == 0:
                raise ToolError(f"not-found: {path} isn't on the stage")
            self.db.execute("insert into changes (path, change, author, note) values (?, 'deleted', ?, ?)",
                            (path, author, note))
        return self.marker()

    def list(self, folder: str) -> list[str]:
        prefix = folder.rstrip("/") + "/" if folder else ""
        paths = [r[0] for r in self.db.execute("select path from files where path like ? escape '!' order by path",
                                               (prefix.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%",))]
        if folder and not paths:
            raise ToolError(f"not-found: {folder} is not a folder on the stage")
        return paths

    def changes(self, since: str | None) -> dict:
        start = int(since) if since else 0
        if since is not None and (not since.isdigit() or start > int(self.marker())):
            raise ToolError(f"unknown-marker: {since!r} is not a change marker this stage gave")
        rows = self.db.execute("select path, change from changes where id > ? order by id", (start,)).fetchall()
        return {"changes": [{"path": p, "change": c} for p, c in rows], "marker": self.marker()}


def checked(path: str) -> str:
    if not path or BAD_PATH.search(path):
        raise ToolError(f"invalid-path: {path!r} is not a stage path")
    return path


class OneToken:
    def __init__(self, token: str):
        self.token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        return AccessToken(token=token, client_id="director", scopes=[]) if secrets.compare_digest(token, self.token) \
            else None


def build_app(db: Path, token: str, host: str = "127.0.0.1"):
    """The server as an ASGI app, answering at /mcp."""
    store = Store(db)
    server = MCPServer("sqlite-stage", instructions="A Zanni stage kept in SQLite.", token_verifier=OneToken(token),
                       auth=AuthSettings(issuer_url="http://127.0.0.1", resource_server_url=None), log_level="WARNING")

    @server.tool()
    def stage_read(path: str) -> str:
        """Read a file from the stage."""
        return store.read(checked(path))

    @server.tool()
    def stage_write(path: str, content: str, author: str | None = None, note: str | None = None) -> str:
        """Write a whole file, replacing it if it exists. `author` and `note` are who wrote it, and why."""
        return store.write(checked(path), content, author, note)

    @server.tool()
    def stage_list(path: str = "") -> list[str]:
        """List the files under a folder; empty for the whole stage."""
        return store.list(path)

    @server.tool()
    def stage_delete(path: str, author: str | None = None, note: str | None = None) -> str:
        """Delete a file."""
        return store.delete(checked(path), author, note)

    @server.tool()
    def stage_changes(since: str | None = None) -> dict:
        """What changed since a change marker (or since the start), and the current marker."""
        return store.changes(since)

    security = None if host in ("127.0.0.1", "localhost", "::1") else TransportSecuritySettings(
        enable_dns_rebinding_protection=False)
    return server.streamable_http_app(stateless_http=True, json_response=True, host=host,
                                      transport_security=security), store


def seed(store: Store, folder: Path) -> int:
    """Load a folder's text files onto an empty stage, so a play can start from them."""
    count = 0
    for file in sorted(p for p in folder.rglob("*") if p.is_file()):
        store.write(file.relative_to(folder).as_posix(), file.read_text(), None, "seed")
        count += 1
    return count


def main() -> int:
    import uvicorn

    parser = argparse.ArgumentParser(description="A Zanni stage kept in SQLite, served over MCP.")
    parser.add_argument("--db", required=True, help="the SQLite file; created when missing")
    parser.add_argument("--listen", default="127.0.0.1:8800", help="host:port (default 127.0.0.1:8800)")
    parser.add_argument("--seed", help="a folder whose files are loaded onto the stage when it is empty")
    args = parser.parse_args()
    token = os.environ.get("ZANNI_STAGE_TOKEN")
    if not token:
        print("ZANNI_STAGE_TOKEN isn't set; set it to the token the director will present", file=sys.stderr)
        return 2
    host, _, port = args.listen.rpartition(":")
    app, store = build_app(Path(args.db), token, host or "127.0.0.1")
    if args.seed and store.marker() == "0":
        print(f"Seeded the stage with {seed(store, Path(args.seed))} file(s) from {args.seed}")
    print(f"Serving the stage in {args.db} at http://{host or '127.0.0.1'}:{port}/mcp")
    uvicorn.run(app, host=host or "127.0.0.1", port=int(port), log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
