"""Protocol conformance: the casting messages, checked against the published JSON Schemas only.

Uses nothing from this codebase, so another implementation can run it on its own messages:
put them in protocol/valid/ or protocol/invalid/, or point ZANNI_PROTOCOL_DIR at a folder laid out the same way.
"""

import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

HERE = Path(__file__).parent
SCHEMAS = HERE.parents[1] / "docs" / "spec" / "schemas"
CASES = Path(os.environ.get("ZANNI_PROTOCOL_DIR", HERE / "protocol"))


def validator(doc: dict) -> Draft202012Validator:
    """The schema is chosen by the message's `kind`."""
    schema = json.loads((SCHEMAS / f"{doc['kind']}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def pointer(error) -> str:
    return "".join(f"/{p}" for p in error.absolute_path)


def walk(errors):
    """Every error, including those inside anyOf/oneOf branches, which jsonschema reports on the parent."""
    for e in errors:
        yield e
        yield from walk(e.context or [])


def cases(folder: str) -> list[Path]:
    return sorted((CASES / folder).glob("*.json"))


@pytest.mark.parametrize("path", cases("valid"), ids=lambda p: p.stem)
def test_valid_message(path):
    doc = json.loads(path.read_text())
    errors = [f"{pointer(e) or '/'}: {e.message}" for e in validator(doc).iter_errors(doc)]
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("path", cases("invalid"), ids=lambda p: p.stem)
def test_invalid_message(path):
    doc = json.loads(path.read_text())
    want = path.with_suffix(".expected").read_text().partition(":")[2].strip()
    found = [pointer(e) for e in walk(validator(doc).iter_errors(doc))]
    assert found, "expected the message to be rejected"
    assert want in found, f"expected an error at {want or '/'}; got errors at {[f or '/' for f in found]}"
