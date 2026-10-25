# Unit converter

A web page where someone types a value, picks the unit it is in and the unit they want, and sees the result: lengths
first (metres, kilometres, centimetres, inches, feet, miles), then weights. Wrong input gets a clear message, never a
crash.

## The project

- **Stack:** Python 3.12, standard library only: the page is served with `http.server`. No other dependencies.
- **Tests:** pytest, under `tests/`, run with `uv run --with pytest python -m pytest -q tests --ignore=tests/findings`.
- **Starting the app:** `uv run python -m app`, listening on 127.0.0.1 at the port in the `PORT` environment
  variable (8000 when it isn't set).
