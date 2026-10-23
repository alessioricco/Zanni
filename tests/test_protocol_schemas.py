"""The published schemas are generated from src/zanni/protocol/; they must not drift."""

import json
from pathlib import Path

import pytest

from zanni.protocol.messages import MESSAGES
from zanni.protocol.schemas import ROOT, render, schemas

VALID = Path(__file__).parent / "conformance" / "protocol" / "valid"


def test_published_schemas_match_the_models():
    published = {p.name for p in ROOT.glob("*.schema.json")}
    generated = schemas()
    assert published == set(generated), "run: uv run python -m zanni.protocol.schemas"
    for name, schema in generated.items():
        assert (ROOT / name).read_text() == render(schema), f"{name} is stale; run: uv run python -m zanni.protocol.schemas"


@pytest.mark.parametrize("path", sorted(VALID.glob("*.json")), ids=lambda p: p.stem)
def test_valid_examples_also_pass_the_models(path):
    """The models add checks a schema can't express (a range going down); valid examples must pass them too."""
    from zanni.protocol.card import ActorCardParams, DirectorCardParams
    doc = json.loads(path.read_text())
    model = {**MESSAGES, "zanni.actor-card": ActorCardParams, "zanni.director-card": DirectorCardParams}[doc["kind"]]
    model.model_validate(doc)
