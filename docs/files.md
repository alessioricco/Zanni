# Zanni files

There is one command, `zanni <file>`, and three kinds of file. The kind comes from the file's keys:

| Kind | Recognised by | What `zanni` would run | Spec |
|---|---|---|---|
| Actor file | `role` and `play` | an actor that joins the play | [Actor file](spec/actor-file.md) |
| Play file | `cast` | the play's director | [Play folder](spec/play-folder.md) |
| Role manifest (`role.yaml`) | `mission` | nothing; it is validated | [Role package](spec/role-package.md) |

These rules apply to all three:

- **Unknown keys are errors.** A typo gets a "did you mean".
- **Duplicate keys are errors.**
- **No secrets:** keys that look like secrets are rejected.
- **Defaults everywhere:** a file only says what differs from the defaults. The spec pages list every field with its default.
- **Versions are text:** write role versions as `1.4.0` or `"1.4"`. Unquoted, `1.4` is read as a number.

## Examples

- **Actor file:** `examples/tester.yaml`
- **Play file:** `examples/plays/habit-tracker/play.yaml`
- **Role manifest:** `examples/roles/tester/role.yaml`
