import pytest

from app.convert import convert


def test_r1_1_km_to_m():
    assert convert(1, "km", "m") == 1000


def test_r1_2_in_to_cm():
    assert convert(12, "in", "cm") == pytest.approx(30.48)
