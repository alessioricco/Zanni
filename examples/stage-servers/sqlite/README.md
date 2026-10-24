# A stage server, in SQLite

An example of the `mcp` stage backend (D47): a play's stage kept in a SQLite file, served over MCP. Any server that offers the same five tools can be a stage; this one is a starting point to copy for a stage kept somewhere else.

```bash
export ZANNI_STAGE_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
uv run python examples/stage-servers/sqlite/server.py --db notes.db --listen 127.0.0.1:8800 --seed ./some-folder
```

- **The play** names it with `stage: { backend: mcp, url: http://127.0.0.1:8800/mcp }`.
- **The director** presents the same `ZANNI_STAGE_TOKEN`, from its configuration's `credentials`. Seats never see it.
- **`--seed`** loads a folder's text files onto an empty stage.
- **Who wrote what:** each file keeps its `author` (the seat) and `note` (the cue), and `changes` lists every write and delete in order.

See [Writing a stage server](../../../docs/writing-a-stage-server.md) for the contract.
