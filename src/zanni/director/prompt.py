"""What the director's model is told once per turn: its role, the script and the play's rules (D33).

The state of the play comes separately, at the start of every turn, from `Production.summary`.
"""

from pathlib import Path

from zanni.files.schemas import PlayFile, Script

ROLE = Path(__file__).parent / "role"


def instructions(script: Script, prose: str, play: PlayFile) -> str:
    rules = play.house_rules
    parts = []
    for name, part in script.parts.items():
        entry = play.cast.get(name)
        bits = [f"{(entry.seats if entry and entry.seats else part.seats)} seat(s)"]
        if part.writes is not None:
            bits.append(f"writes {', '.join(part.writes) or 'nothing'}")
        if part.description:
            bits.append(part.description)
        if entry is None:
            bits.append("not cast in this play")
        parts.append(f"- **{name}**: {'; '.join(bits)}")
    verifiers = [f"- `{n}`: {v.description}" for n, v in script.verifiers.items()] or ["- none"]
    stop = []
    if script.stop.max_rounds:
        stop.append(f"at most {script.stop.max_rounds} round(s)")
    if script.stop.budget_per_round is not None:
        stop.append(f"at most ${script.stop.budget_per_round:.2f} per round")
    if script.stop.done_when:
        stop.append(f"done when {', '.join(script.stop.done_when)} pass")
    enforced = []
    for gate in script.gates:
        if gate.name in rules.gates:
            when = "every round" if gate.every == "round" else "once"
            enforced.append(f"{gate.name} ({when}{', before any cue to ' + ', '.join(gate.before) if gate.before else ''})")
    house = [f"budget: {'$' + format(rules.budget, '.2f') if rules.budget is not None else 'none'}",
             f"gates this play enforces: {', '.join(enforced) or 'none'} (the others are skipped)",
             f"at most {rules.max_director_turns} of your turns per round"]
    return "\n".join([
        (ROLE / "AGENTS.md").read_text().strip(), "",
        f"# The play: {play.name}", "",
        f"**Mission:** {script.mission}", "",
        "## Parts", *parts, "",
        "## Verifiers", *verifiers, "",
        f"**Stop rules:** {'; '.join(stop) or 'none'}.",
        f"**House rules:** {'; '.join(house)}.", "",
        f"## The script: {script.name} {script.version}", "",
        prose.strip(),
    ])
