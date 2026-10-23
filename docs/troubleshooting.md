# Troubleshooting

Each problem `zanni` reports already says what to change. This page explains the common ones.

## "is not an actor file, a play file or a role manifest"

```
notes.yaml: is not an actor file, a play file or a role manifest; each kind needs these fields: actor file: `play` and `role`; play file: `cast`; role manifest: `mission`
```

`zanni` recognises a file by its keys. Add the key that marks the kind you meant. If you misspelled one of those keys, `zanni` points at it instead:

```
role.yaml, line 3, mision: is not a known field; did you mean `mission`?
```

## "looks like more than one kind of file"

The file has the marking keys of two kinds, such as `role` and `play` and also `cast`. An actor file and a play file are separate files: split it in two.

## "is not a known field"

```
play.yaml, line 9, cast.coder.hots: is not a known field; did you mean `host`?
```

Unknown keys are always errors, so a typo can never silently turn into a default. Fix the spelling, or remove the key. The full field lists are in the [spec](spec/README.md).

## "looks like a secret"

```
tester.yaml, line 3, anthropic_api_key: looks like a secret, and Zanni files never hold secrets; remove it and set the value in the environment or a git-ignored .env
```

Move the value to the environment or a `.env` file; see [Models and keys](models-and-keys.md). Any key containing the word `key`, `token`, `secret` or `password` is treated as a secret, wherever it appears in the file.

## "has no version"

```
tester.yaml, line 1, role: "github.com/someone/tester" has no version; write it as github.com/someone/tester@1.0.0, with the version you want
```

A remote role reference needs a version: `github.com/someone/tester@1.4.0`. A local folder needs none: `roles/tester`.

## "was read as a number"

```
role.yaml, line 2, version: 1.4 was read as a number; write the version in quotes as major.minor.patch, e.g. "1.4.0"
```

YAML reads `1.4` as a number. Write versions with three parts, which YAML keeps as text (`1.4.0`), or put them in quotes.

## Seats

```
play.yaml, line 4, cast.coder.seats: the range 4-1 goes down; write the smaller number first: 1-4
play.yaml, line 5, cast.tester.seats: "many" is not a number of seats; write a number such as 2, or a range such as 1-4
```

Seats are a number of at least 1, or a range written smaller number first.

## "is not a director address"

```
play.yaml, line 2, director: "director.example.com" is not a director address; write a URL such as wss://director.example.com
```

The director is a URL starting with `ws://`, `wss://`, `http://` or `https://`. Leave the field out to run the director on this machine.

## "appears twice"

```
play.yaml, line 2, name: appears twice; keep one of the two entries
```

Plain YAML would silently keep the last value, so `zanni` refuses instead.

## "is not valid YAML"

```
play.yaml, line 2: is not valid YAML: mapping values are not allowed here; check the indentation and the quotes on this line and the one before
```

This is usually indentation: nested fields need the same number of spaces, and tabs aren't allowed. Text that contains `: ` needs quotes.

## Still stuck?

[Open an issue](https://github.com/alessioricco/zanni/issues). Include the file, the exact output, and `zanni --version`.
