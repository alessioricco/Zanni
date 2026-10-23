"""What `zanni <file>` would run, in a few lines."""

from zanni.files.schemas import ActorConfiguration, PlayFile, RoleManifest, Script


def summarise(doc: ActorConfiguration | PlayFile | RoleManifest | Script) -> list[str]:
    if isinstance(doc, ActorConfiguration):
        who = f"'{doc.name}'" if doc.name else "an actor"
        return [f"Actor configuration: would start {who}, playing a role in a play.",
                f"  role: {doc.role}", f"  play: {doc.play}"]
    if isinstance(doc, PlayFile):
        lines = [f"Play file: would start the director for the play '{doc.name}'.",
                 f"  script: {doc.script}",
                 f"  director: {doc.director or 'this machine'}", f"  stage: {doc.stage}", "  cast:"]
        for name, entry in doc.cast.items():
            host = f", started here ({entry.host})" if entry.host == "local" else (f", on {entry.host}" if entry.host else "")
            lines.append(f"    {name}: {entry.role}, {entry.seats} seat{'s' if entry.seats.max > 1 else ''}{host}")
        rules = doc.house_rules
        budget = f"${rules.budget:.2f}" if rules.budget is not None else "none set"
        lines.append(f"  house rules: budget {budget}; human gates: {', '.join(rules.gates) or 'none'}")
        return lines
    if isinstance(doc, Script):
        lines = [f"Script: '{doc.name}' {doc.version}.", f"  mission: {doc.mission}", "  parts:"]
        for name, part in doc.parts.items():
            bits = [f"{part.seats} seat{'s' if part.seats.max > 1 else ''}"]
            if part.optional:
                bits.append("optional")
            if part.writes is not None:
                bits.append(f"writes {', '.join(part.writes) or 'nothing'}")
            if part.suggested:
                bits.append(f"suggested role {part.suggested}")
            lines.append(f"    {name}: {'; '.join(bits)}")
        lines.append(f"  gates: {', '.join(doc.gates) or 'none'}")
        rules = [f"at most {doc.stop.max_rounds} rounds"] if doc.stop.max_rounds else []
        if doc.stop.budget_per_round is not None:
            rules.append(f"${doc.stop.budget_per_round:.2f} per round")
        lines.append(f"  stop rules: {'; '.join(rules) or 'none in the frontmatter'}")
        return lines
    return [f"Role manifest: the role '{doc.name}' {doc.version}.", f"  mission: {doc.mission}",
            f"  stage: reads {', '.join(doc.needs.stage_read) or 'nothing'}; "
            f"writes {', '.join(doc.needs.stage_write) or 'nothing'}",
            f"  tools: {', '.join(doc.needs.tools) or 'none'}", f"  never: {'; '.join(doc.never) or 'no rules'}"]
