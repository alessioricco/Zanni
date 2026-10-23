# Actor configuration

An actor configuration is one actor instance's own file. A zanni is an empty shell; this file tells it which role to play, which play to join and, as this page grows, which models to run and which credentials to use. It holds what is specific to this instance, never the role's capabilities (D14). It stays on the actor's machine and never goes in a repository.

```yaml
# tester.yaml
name: tester-1
role: github.com/someone/tester@1.4.0
play: https://example.com/plays/habit-tracker/play.yaml
```

It is recognised by having both `role` and `play`, and it is the file passed to `zanni` to start an actor.

## Fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `name` | text | no | none | the actor | This instance's name, used in the log and in summaries. |
| `role` | package reference | yes | — | the director, at casting | The role this actor plays. The director casts the actor only if the reference matches the role cast for a part. |
| `play` | URL or path | yes | — | the actor | The play file to join. The actor decides which plays and directors it is willing to join. |

## Package references

Roles and scripts are both referenced as packages, in one of two ways:

- **A remote package:** `host/owner/name@version`, such as `github.com/someone/tester@1.4.0`. The version is required. A play's lockfile pins each one to a commit.
- **A local folder:** a path with no host, such as `roles/tester` or `./roles/tester`.

## Draft

- **Models and credentials:** the `models` list (D11) and the `credentials` section (D15), and the state folder and port.
