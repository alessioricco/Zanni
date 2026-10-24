"""The JSON Lines logs: the play's, kept by the director, and each actor's own (D18, D32)."""

import json
from datetime import UTC, datetime
from pathlib import Path


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Log:
    """One JSON object per line, appended. Never holds a credential or a token (D15, D24)."""

    def __init__(self, path: Path, run_id: str):
        self.path, self.run_id = path, run_id
        path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event: str, **fields) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps({"ts": now(), "run": self.run_id, "event": event, **fields}) + "\n")
