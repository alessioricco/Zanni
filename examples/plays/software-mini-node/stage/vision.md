# Unit converter

A web page where someone types a value, picks the unit it is in and the unit they want, and sees the result: lengths
first (metres, kilometres, centimetres, inches, feet, miles), then weights. Wrong input gets a clear message, never a
crash.

## The project

- **Stack:** Node.js 22, JavaScript modules, no dependencies: the page is served with `node:http`.
- **Tests:** `node:test`, as `tests/*.test.js`, run with `npm test`. Tests under `tests/findings/` aren't run by it.
- **Starting the app:** `node app/server.js`, listening on 127.0.0.1 at the port in the `PORT` environment variable
  (8000 when it isn't set).
