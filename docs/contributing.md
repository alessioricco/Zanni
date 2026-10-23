# Contributing

Zanni is early, and the most useful contributions now are to the spec: the formats, the rules, and conformance cases that pin them down. Code changes are welcome too, and every change follows the rules below.

## Set up

```bash
git clone https://github.com/alessioricco/zanni.git
cd zanni
uv sync                    # installs Zanni and the dev dependencies
uv run pytest              # the full suite; no API key, no network, no model needed
scripts/get-skills.sh      # optional: the agent skills, if you work with a coding agent
```

You need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/) and git. A local model server and API keys are optional, and nothing in the test suite uses them.

## The rules every change follows

These are the project's golden rules, kept in [AGENTS.md](../AGENTS.md) so that people and coding agents follow the same ones:

1. **Docs in the same change.** A change to a command, a file format, a setting, a behaviour or a known limitation updates the matching page under `docs/` in the same commit.
2. **Spec and code together.** A change to the role package, the script, the play file, the actor configuration, the stage or the casting extension updates the [spec](spec/README.md) and the [conformance tests](testing.md#conformance-tests) in the same commit.
3. **Standards first.** Before adding a format or protocol, check whether AGENTS.md, skills, MCP or A2A already covers it. Record in [DECISIONS.md](../DECISIONS.md) why a gap needed something new.
4. **Engine independence.** No role, script, play or protocol message refers to Pydantic AI, a specific MCP server or a model vendor. Only the engine adapter (`src/zanni/engine/`) may import Pydantic AI, `mcp` or `a2a-sdk`.
5. **Limits are enforced where they can't be bypassed.** Every permission or limit names the component that enforces it: the stage, the director, a verifier or the actor (through its configuration). Never the actor's own goodwill.
6. **Local first, cloud never worse.** Actors must work on local models without making cloud models worse. Strategies for weaker models are opt-in.
7. **Measure before claiming.** Claims about quality or portability come from conformance tests and recorded runs, never from a single run.
8. **Verify before using.** Pydantic AI, `mcp` and `a2a-sdk` change fast. Check every symbol against the installed package or its current docs.

Also:

- **No secrets in shared files.** Never commit, print or log a real API key, and no option takes one. Roles, scripts and plays never hold secrets; only an actor configuration may, under the safeguards of D15. Tests use obviously fake keys.
- **No assumptions about a contributor's machine.** Don't hard-code hosts, ports or model tags. Live tests that need a model skip with a clear message when none is configured.

## Making a change

1. **Branch:** create a branch from `master`.
2. **Commit:** keep each commit to one change, with its code, tests and docs together. The commit message says what changed and why.
3. **Test:** `uv run pytest` must pass. CI runs it on Python 3.12 and 3.14.
4. **Decisions:** if the change makes a decision (a new format, a new dependency, a rule), add an entry to `DECISIONS.md`. Use the next number, with what was decided, why, and what would make us revisit it. Never edit an old decision: supersede it with a new one.
5. **Pull request:** open one against `master`, saying what changed, why, and how you checked it.

### Adding or changing a field in a Zanni file

This touches four places, all in one commit:

1. **The schema:** `src/zanni/files/schemas.py`. Give the field a default when the vision says "defaults everywhere", and a validator that raises `ValueError("problem; what to change")` for values that need a plain-words message.
2. **The spec page:** add a row to the field table in `docs/spec/`, with the type, whether it's required, the default, the component that enforces it, and the meaning.
3. **Conformance cases:** add at least one valid file, and one invalid file with its `.expected` sidecar, under `tests/conformance/` ([Testing](testing.md#conformance-tests)).
4. **User docs:** update `docs/files.md`, or the matching page, if users need to know.

### Version updates of the engine's dependencies

`pydantic-ai-slim`, `mcp` and `a2a-sdk` are pinned to exact versions (D8). To upgrade one:

1. Change the pin.
2. Run `uv lock`.
3. Run the full suite, including the conformance tests.
4. Say in the commit what changed upstream that matters to Zanni.

## Where things are

- **[Architecture](architecture.md):** the code.
- **[Testing](testing.md):** the tests.
- **[Coding agents and skills](agent-skills.md):** working with Claude Code or another agent.
- **[Roadmap](../ROADMAP.md):** what comes next, and what "done" means for each milestone.
- **[Vision](../Zanni%20vision.md):** the full design, including the open questions.

## Writing style for docs

- Plain words, short sentences, and examples that were actually run.
- Use the five theatre words (role, actor, director, stage, play) exactly, and plain words for everything else.
- Name what doesn't work yet, rather than leaving it out.
