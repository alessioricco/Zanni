"""Generate the casting extension's JSON Schemas into docs/spec/schemas/.

Run: uv run python -m zanni.protocol.schemas
A test fails if the published schemas differ from what this produces.
"""

import json
import sys
from pathlib import Path

from zanni.protocol.card import ActorCardParams, DirectorCardParams
from zanni.protocol.messages import MESSAGES

ROOT = Path(__file__).resolve().parents[3] / "docs" / "spec" / "schemas"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schemas() -> dict[str, dict]:
    """File name -> schema. One per message kind, and one per card's params."""
    models = {**MESSAGES, "zanni.actor-card": ActorCardParams, "zanni.director-card": DirectorCardParams}
    out = {}
    for kind, model in sorted(models.items()):
        schema = {"$schema": DRAFT, "$id": f"{kind}.schema.json", **model.model_json_schema()}
        out[f"{kind}.schema.json"] = schema
    return out


def render(schema: dict) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas().items():
        (ROOT / name).write_text(render(schema))
        print(f"wrote docs/spec/schemas/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
