"""Casting messages in and out of A2A messages: one data part tagged by `kind`, listing the extension (D21)."""

import uuid

from a2a.types import AgentCard, Message, TaskState
from google.protobuf.json_format import MessageToDict, ParseDict
from pydantic import ValidationError

from zanni.protocol.card import EXTENSION_URI
from zanni.protocol.encoding import Wire
from zanni.protocol.messages import MESSAGES

STATES = {
    "working": TaskState.TASK_STATE_WORKING,
    "input-required": TaskState.TASK_STATE_INPUT_REQUIRED,
    "completed": TaskState.TASK_STATE_COMPLETED,
    "canceled": TaskState.TASK_STATE_CANCELED,
    "rejected": TaskState.TASK_STATE_REJECTED,
}
STATE_NAMES = {v: k for k, v in STATES.items()}
EXTENSIONS_HEADER = "A2A-Extensions"


class BadMessage(ValueError):
    """A message that isn't one casting message, valid against its schema."""


def as_json(message: Wire) -> dict:
    """A casting message as it travels: every field present, numbers already strings (D23)."""
    return message.model_dump(mode="json")


def to_a2a(message: Wire, *, task_id: str = "", context_id: str = "", role: str = "ROLE_AGENT") -> Message:
    return ParseDict({"messageId": uuid.uuid4().hex, "role": role, "taskId": task_id, "contextId": context_id,
                      "extensions": [EXTENSION_URI], "parts": [{"data": as_json(message)}]}, Message())


def data_of(message: Message) -> dict | None:
    """The message's casting payload, if it has one data part; no validation."""
    data = [MessageToDict(p)["data"] for p in message.parts if p.HasField("data")]
    return data[0] if len(data) == 1 and isinstance(data[0], dict) else None


def from_a2a(message: Message, *kinds: str) -> Wire:
    """Parse and validate the casting message in an A2A message; `kinds` limits which are accepted."""
    if EXTENSION_URI not in message.extensions:
        raise BadMessage(f"the message doesn't list the casting extension ({EXTENSION_URI})")
    data = data_of(message)
    if data is None:
        raise BadMessage("the message must hold exactly one data part, a casting message")
    kind = data.get("kind")
    if kind not in MESSAGES or (kinds and kind not in kinds):
        allowed = ", ".join(kinds or MESSAGES)
        raise BadMessage(f"{kind!r} is not a message accepted here; expected one of: {allowed}")
    try:
        return MESSAGES[kind].model_validate(data)
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(map(str, err['loc'])) or kind}: {err['msg']}" for err in e.errors())
        raise BadMessage(f"{kind} isn't valid: {problems}") from None


def join_problem(message: Message) -> str | None:
    """Why a join can't be considered, as `<reason>: <message>` (bad-card or unsupported-version), or None."""
    data = data_of(message) or {}
    card = data.get("card")
    if isinstance(card, dict):
        uris = [e.get("uri", "") for e in card.get("capabilities", {}).get("extensions", []) if isinstance(e, dict)]
        base = EXTENSION_URI.split("#")[0]
        if EXTENSION_URI not in uris and any(u.split("#")[0] == base for u in uris):
            return (f"unsupported-version: the card speaks the casting extension at "
                    f"{', '.join(u for u in uris if u.startswith(base))}; this director speaks {EXTENSION_URI}")
    try:
        join = from_a2a(message, "zanni.join")
    except BadMessage as e:
        return f"bad-card: {e}"
    try:
        ParseDict(join.card, AgentCard())
    except Exception as e:
        return f"bad-card: the card isn't an A2A Agent Card: {str(e)[:200]}"
    return None
