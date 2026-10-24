"""The casting messages survive a2a-sdk unchanged (D23): through a data part, and through card extension params.

Tests may import a2a-sdk; Zanni's own code outside the engine adapter may not (golden rule 4).
"""

import json
from pathlib import Path

import pytest
from a2a.types import AgentCard, Message
from google.protobuf.json_format import MessageToDict, MessageToJson, Parse, ParseDict

VALID = Path(__file__).parents[1] / "conformance" / "protocol" / "valid"
URI = "https://github.com/alessioricco/Zanni/blob/master/docs/spec/casting-extension.md#v3"


def same(a, b) -> bool:
    """Equal, and every value of the same type: 4 and 4.0 are equal in Python but not the same on the wire."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


@pytest.mark.parametrize("path", sorted(VALID.glob("*.json")), ids=lambda p: p.stem)
def test_message_survives_a_data_part(path):
    doc = json.loads(path.read_text())
    msg = ParseDict({"messageId": "m1", "role": "ROLE_USER", "extensions": [URI], "parts": [{"data": doc}]}, Message())
    back = MessageToDict(Parse(MessageToJson(msg), Message()))["parts"][0]["data"]
    assert same(back, doc), f"{path.name} changed on the way through a2a-sdk"


@pytest.mark.parametrize("name", ["actor-card", "director-card"])
def test_card_params_survive_an_agent_card(name):
    params = json.loads((VALID / f"{name}.json").read_text())
    card = ParseDict({"name": "x", "capabilities": {"extensions": [{"uri": URI, "params": params}]}}, AgentCard())
    back = MessageToDict(Parse(MessageToJson(card), AgentCard()))["capabilities"]["extensions"][0]["params"]
    assert same(back, params)
