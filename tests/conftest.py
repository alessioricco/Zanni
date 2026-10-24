"""Every test leaves examples/ as it found it: an example's stage is copied before anything runs on it (D40)."""

from pathlib import Path

import pytest

from zanni.files.hashing import package_hash

EXAMPLES = Path(__file__).parents[1] / "examples"


@pytest.fixture(scope="session", autouse=True)
def examples_unchanged():
    before = package_hash(EXAMPLES)
    yield
    assert package_hash(EXAMPLES) == before, "the test suite changed examples/; run examples from a copy"
