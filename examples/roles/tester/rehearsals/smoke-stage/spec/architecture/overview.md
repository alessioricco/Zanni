# Architecture

- `app/convert.py`: `convert(value: float, from_unit: str, to_unit: str) -> float`; units `m`, `km`, `cm`, `in`.
  Raises `ValueError` for an unknown unit. Serves R1-1 and R1-2.
- Tests: pytest, under `tests/`, run with `uv run --with pytest python -m pytest -q tests`.
