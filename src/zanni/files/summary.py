"""What `zanni <file>` would run, in a few lines."""

from zanni.files.schemas import ActorFile, PlayFile, RoleManifest


def summarise(doc: ActorFile | PlayFile | RoleManifest) -> list[str]:
    if isinstance(doc, ActorFile):
        return ["Actor file: would start an actor that joins a play.",
                f"  role: {doc.role}", f"  play: {doc.play}"]
    if isinstance(doc, PlayFile):
        lines = [f"Play file: would start the director for the play '{doc.name}'.",
                 f"  director: {doc.director or 'this machine'}", f"  stage: {doc.stage}"]
        if doc.script:
            lines.append(f"  script: {doc.script}")
        lines.append("  cast:")
        for name, entry in doc.cast.items():
            host = f", started here ({entry.host})" if entry.host == "local" else (f", on {entry.host}" if entry.host else "")
            lines.append(f"    {name}: {entry.role}, {entry.seats} seat{'s' if entry.seats.max > 1 else ''}{host}")
        rules = doc.house_rules
        budget = f"${rules.budget:.2f}" if rules.budget is not None else "none set"
        lines.append(f"  house rules: budget {budget}; human gates: {', '.join(rules.gates) or 'none'}")
        return lines
    return [f"Role manifest: the role '{doc.name}' {doc.version}.", f"  mission: {doc.mission}",
            f"  stage: reads {', '.join(doc.needs.stage_read) or 'nothing'}; "
            f"writes {', '.join(doc.needs.stage_write) or 'nothing'}",
            f"  tools: {', '.join(doc.needs.tools) or 'none'}", f"  never: {'; '.join(doc.never) or 'no rules'}"]
