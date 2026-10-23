"""What `zanni <file>` would run, in a few lines."""

from zanni.files.schemas import ActorConfiguration, Lockfile, PlayFile, Rehearsal, RoleManifest, Script, Seats


def summarise(doc: ActorConfiguration | PlayFile | RoleManifest | Script | Lockfile | Rehearsal) -> list[str]:
    if isinstance(doc, ActorConfiguration):
        who = f"'{doc.name}'" if doc.name else "an actor"
        lines = [f"Actor configuration: would start {who}, playing a role in a play.",
                 f"  role: {doc.role}", f"  play: {doc.play}", "  models, in order:"]
        for i, m in enumerate(doc.models, start=1):
            bits = [f"{m.provider} {m.model}"]
            if m.base_url:
                bits.append(f"at {m.base_url}")
            if m.tool_format == "text":
                bits.append("text tool format")
            if m.price:
                bits.append(f"${m.price.input}/${m.price.output} per million tokens")
            lines.append(f"    {i}. {', '.join(bits)}")
        stored = set(doc.stored_credentials())
        # Credential values are never shown (D15): only their names, and where each one comes from.
        creds = [f"{k} ({'stored, hidden' if k in stored else 'from the environment'})" for k in doc.credentials]
        lines.append(f"  credentials: {', '.join(creds) or 'none; models use their usual environment variables'}")
        state = doc.state_dir or f"~/.zanni/actors/{doc.name or '<name>'}"
        lines.append(f"  state: {state}")
        return lines
    if isinstance(doc, PlayFile):
        lines = [f"Play file: would start the director for the play '{doc.name}'.",
                 f"  script: {doc.script}",
                 f"  director: {doc.director or 'this machine'}", f"  stage: {doc.stage}", "  cast:"]
        for name, entry in doc.cast.items():
            host = f", started here ({entry.host})" if entry.host == "local" else (f", on {entry.host}" if entry.host else "")
            seats = entry.seats or Seats(min=1, max=1)
            lines.append(f"    {name}: {entry.role}, {seats} seat{'s' if seats.max > 1 else ''}{host}")
        rules = doc.house_rules
        budget = f"${rules.budget:.2f}" if rules.budget is not None else "none set"
        cap = f"; at most {rules.max_seats_per_host} seats per host" if rules.max_seats_per_host else ""
        lines.append(f"  house rules: budget {budget}; human gates: {', '.join(rules.gates) or 'none'}{cap}")
        return lines
    if isinstance(doc, Rehearsal):
        lines = [f"Rehearsal: '{doc.rehearsal}', run with no director when an actor configuration's `play` points here.",
                 f"  stage: {doc.stage} (copied fresh for every run)", "  cues:"]
        lines += [f"    {i}. {cue.scene}: {cue.instructions[:70]}" for i, cue in enumerate(doc.cues, start=1)]
        lines.append(f"  verify: {', '.join(v.name for v in doc.verify) or 'nothing'}")
        return lines
    if isinstance(doc, Lockfile):
        lines = ["Lockfile: pins a play's script and roles."]
        for ref, pin in [*doc.script.items(), *doc.roles.items()]:
            lines.append(f"  {ref}: {('commit ' + pin.commit[:12]) if pin.commit else 'local'}, {pin.hash[:19]}…")
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
