"""Validate loaded data against a Pydantic model and turn every problem into a plain-words error."""

import difflib
import re
import typing
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from zanni.files.errors import FileError, FileErrors, Path
from zanni.files.loader import Loaded

M = TypeVar("M", bound=BaseModel)

SECRET_WORDS = {"key", "apikey", "token", "secret", "password", "passwd"}

_TYPE_NAMES = {
    "string_type": "text", "int_type": "a whole number", "int_parsing": "a whole number",
    "float_type": "a number", "float_parsing": "a number", "decimal_type": "a number", "decimal_parsing": "a number",
    "bool_type": "true or false", "bool_parsing": "true or false",
    "list_type": "a list", "dict_type": "a set of `name: value` fields", "model_type": "a set of `name: value` fields",
    "model_attributes_type": "a set of `name: value` fields",
}


HIDDEN = object()


def _describe(value: Any) -> str:
    if value is HIDDEN:
        return "a value (hidden)"
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, (int, float)):
        return f"the number {value}"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a set of fields"
    return "nothing" if value is None else type(value).__name__


def _models_in(annotation: Any) -> list[type[BaseModel]]:
    """Every model a field can hold, looking through Optional, unions, lists and dicts."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [m for arg in typing.get_args(annotation) for m in _models_in(arg)]


def _known_fields(model: type[BaseModel], path: Path) -> list[str]:
    """The field names allowed at `path`, for "did you mean" suggestions."""
    models = [model]
    for part in path:
        inner = [m for mod in models if isinstance(part, str) and part in mod.model_fields
                 for m in _models_in(mod.model_fields[part].annotation)]
        # A list index or a dict key (such as a cast entry's name) stays on the same models.
        models = inner or models
    return sorted({name for m in models for name in m.model_fields})


def _message(err: dict, loaded: Loaded, model: type[BaseModel], hidden: tuple[str, ...] = ()) -> FileError:
    path: Path = tuple(p for p in err["loc"] if p != "[key]")  # Pydantic marks an invalid dict key with "[key]"
    kind = err["type"]
    if path and path[0] in hidden:
        err = {**err, "input": HIDDEN}  # a credential's value never appears in a message (D15)
    if kind == "missing":
        return FileError(loaded.file, loaded.line(path[:-1]) or 1, path, "is required but missing",
                         f"add a `{path[-1]}:` line" + (f" under `{path[-2]}`" if len(path) > 1 else ""))
    if kind == "extra_forbidden":
        known = _known_fields(model, path[:-1])
        close = difflib.get_close_matches(str(path[-1]), known, n=1)
        fix = f"did you mean `{close[0]}`?" if close else f"known fields here: {', '.join(known)}"
        return FileError(loaded.file, loaded.line(path), path, "is not a known field", fix)
    if kind in _TYPE_NAMES:
        return FileError(loaded.file, loaded.line(path), path,
                         f"should be {_TYPE_NAMES[kind]}, not {_describe(err.get('input'))}")
    if kind == "literal_error":
        return FileError(loaded.file, loaded.line(path), path, f"is {_describe(err.get('input'))}",
                         f"use one of: {err['ctx']['expected']}")
    if kind in ("value_error", "assertion_error"):
        # Validators raise ValueError("problem; fix"), already in plain words.
        problem, _, fix = str(err["ctx"]["error"]).partition("; ")
        return FileError(loaded.file, loaded.line(path), path, problem, fix)
    if kind in ("greater_than_equal", "greater_than", "less_than_equal", "less_than"):
        bound = next(iter(err["ctx"].values()))
        words = {"greater_than_equal": "at least", "greater_than": "more than",
                 "less_than_equal": "at most", "less_than": "less than"}[kind]
        return FileError(loaded.file, loaded.line(path), path, f"should be {words} {bound}, not {err.get('input')}")
    return FileError(loaded.file, loaded.line(path), path, f"has a value Zanni can't use ({_describe(err.get('input'))})",
                     "see docs/files.md for this field")


def is_secret_name(name: str) -> bool:
    words = {w.lower() for w in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", name)}
    return bool(words & SECRET_WORDS) or "apikey" in name.lower().replace("_", "").replace("-", "")


def find_secrets(loaded: Loaded, allowed: tuple[str, ...] = ()) -> list[FileError]:
    """Secret-looking keys anywhere, except under the top-level sections in `allowed`."""
    found: list[FileError] = []

    def walk(value: Any, path: Path) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                if not path and k in allowed:
                    continue
                if isinstance(k, str) and is_secret_name(k):
                    fix = ("move it to this file's `credentials` section" if "credentials" in allowed
                           else "remove it; secrets belong in an actor configuration's `credentials`, or the environment")
                    found.append(FileError(loaded.file, loaded.line((*path, k)), (*path, k),
                                           "looks like a secret, and only an actor configuration's `credentials` may hold one",
                                           fix))
                else:
                    walk(v, (*path, k))
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, (*path, i))

    walk(loaded.data, ())
    return found


def validate(loaded: Loaded, model: type[M], *, reject_secrets: bool = True) -> M:
    secret_sections = getattr(model, "SECRET_SECTIONS", ())  # top-level sections allowed to hold secrets (D15)
    errors = find_secrets(loaded, secret_sections) if reject_secrets else []
    try:
        result = model.model_validate(loaded.data)
    except ValidationError as e:
        secret_paths = {x.path for x in errors}  # a secret is reported once, as a secret, not also as unknown
        errors += [_message(err, loaded, model, secret_sections) for err in e.errors(include_url=False)
                   if tuple(err["loc"]) not in secret_paths]
    if errors:
        errors.sort(key=lambda x: (x.line or 0, str(x.path)))
        raise FileErrors(errors)
    return result
