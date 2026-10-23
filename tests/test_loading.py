import pytest
from pydantic import BaseModel, ConfigDict

from zanni.files.errors import FileErrors
from zanni.files.loader import load_text
from zanni.files.validation import validate


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    budget: float = 0
    gates: list[str] = []


class Toy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    limits: Limits = Limits()


def errors_for(text: str) -> list[str]:
    with pytest.raises(FileErrors) as e:
        validate(load_text(text, "toy.yaml"), Toy)
    return [str(x) for x in e.value.errors]


def test_valid_file_loads_with_lines():
    loaded = load_text("name: a\nlimits:\n  budget: 2\n", "toy.yaml")
    assert loaded.line(("limits", "budget")) == 3
    assert validate(loaded, Toy).limits.budget == 2


def test_yaml_syntax_error_has_its_line():
    (msg,) = errors_for("name: a\nlimits:\n  budget: [1, 2\n")
    assert msg.startswith("toy.yaml, line ")
    assert "is not valid YAML" in msg


def test_unknown_key_suggests_the_close_one():
    (msg,) = errors_for("name: a\nlimits:\n  budgte: 2\n")
    assert msg == "toy.yaml, line 3, limits.budgte: is not a known field; did you mean `budget`?"


def test_unknown_key_without_a_close_match_lists_known_fields():
    (msg,) = errors_for("name: a\ncolour: red\n")
    assert msg == "toy.yaml, line 2, colour: is not a known field; known fields here: limits, name"


def test_wrong_type():
    (msg,) = errors_for("name: a\nlimits:\n  budget: lots\n")
    assert msg == 'toy.yaml, line 3, limits.budget: should be a number, not "lots"'


def test_missing_field():
    (msg,) = errors_for("limits:\n  budget: 2\n")
    assert msg == "toy.yaml, line 1, name: is required but missing; add a `name:` line"


@pytest.mark.parametrize("key", ["api_key", "ANTHROPIC_API_KEY", "apiKey", "token", "client_secret", "password"])
def test_secret_looking_key_is_rejected(key):
    (msg,) = errors_for(f"name: a\nlimits:\n  {key}: x\n")
    assert msg.startswith(f"toy.yaml, line 3, limits.{key}: looks like a secret")
    assert "environment or a git-ignored .env" in msg


@pytest.mark.parametrize("key", ["keywords", "monkey", "tokenizer_model"])
def test_ordinary_words_are_not_secrets(key):
    msgs = errors_for(f"name: a\n{key}: x\n")
    assert "looks like a secret" not in msgs[0]


def test_duplicate_key_is_an_error():
    (msg,) = errors_for("name: a\nname: b\n")
    assert msg == "toy.yaml, line 2, name: appears twice; keep one of the two entries"


def test_empty_file():
    (msg,) = errors_for("")
    assert msg == "toy.yaml: is empty; see docs/files.md for what a Zanni file holds"


def test_all_problems_are_reported_together():
    assert len(errors_for("nam: a\nlimits:\n  budget: lots\n")) == 3  # unknown `nam`, missing `name`, bad budget
