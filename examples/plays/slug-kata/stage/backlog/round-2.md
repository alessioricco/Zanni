# Round 2

## slugify's max_length (app/slug.py)
`slugify` gains an optional argument, `max_length: int | None = None`. With it, the slug is cut to at most that many
characters, at the last dash that fits, with no dash at the end; without it, nothing changes.

- AC5: `slugify("Hello Big World", max_length=9)` returns `"hello-big"`.
