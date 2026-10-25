# Architecture

- `app/convert.py`: `convert(value, from_unit, to_unit)`; serves R1-1 and R1-2.
- `app/web.py`: the page at `/`, using `convert`; serves R1-3. It owns the entry point.
