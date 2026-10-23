import pytest
from pydantic import ValidationError

from zanni.protocol.encoding import Money, Range, money


def test_money_is_exact_text():
    assert money("20.10").amount == "20.10"
    assert Money(amount="0", currency="USD").amount == "0"


@pytest.mark.parametrize("bad", ["-1", "1e3", "20,10", "01", " 4", ""])
def test_money_rejects_anything_but_a_plain_decimal(bad):
    with pytest.raises(ValidationError):
        Money(amount=bad, currency="USD")


def test_money_rejects_a_number():
    with pytest.raises(ValidationError):
        Money(amount=20.1, currency="USD")


def test_range_must_go_up():
    assert Range(min="1", max="4").max == "4"
    with pytest.raises(ValidationError, match="min \\(4\\) is more than max \\(1\\)"):
        Range(min="4", max="1")


def test_large_counts_survive_as_text():
    big = str(2**53 + 1)
    assert Range(min="0", max=big).max == "9007199254740993"
