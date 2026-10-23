# Actor file

An actor file says which role an actor plays, and in which play. Everything else comes from the director when the actor is cast. It is the file passed to `zanni` to start an actor:

```yaml
# tester.yaml
role: github.com/someone/tester@1.4.0
play: https://example.com/plays/habit-tracker/play.yaml
```

It is recognised by having both `role` and `play`.

## Fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `role` | role reference | yes | — | the director, at casting | The role this actor plays. The director casts the actor only if the reference matches a role in the play's cast. |
| `play` | URL or path | yes | — | the actor's host | The play file to join. The host decides which plays and directors it is willing to join. |

## Role references

A role reference is one of:

- **A remote role:** `host/owner/name@version`, such as `github.com/someone/tester@1.4.0`. The version is required. A play's `roles.lock` pins each one to a commit.
- **A local folder:** a path with no host, such as `roles/tester` or `./roles/tester`.

**Draft:** how the version resolves to a commit (tags, branches, the lockfile format) is part of the [role package](role-package.md) spec, which isn't written yet.

## Draft

- **Host settings:** the actor's own settings (state folder, port, model catalog) live outside this file, in the host's `models.yaml` and defaults. Their format isn't specified yet.
