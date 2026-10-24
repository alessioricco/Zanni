# slugify
`app.slug.slugify(text: str, max_length: int | None = None) -> str` lowercases the text, turns every run of
characters that are not letters or digits into one dash, and removes dashes at both ends. With `max_length`, the
slug is cut to at most that many characters, at the last dash that fits, with no dash at the end.
Import it as `from app.slug import slugify`.
