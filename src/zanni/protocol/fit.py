"""How the director decides whether an actor's card fits a part (D21). Pure functions, reused by the director."""

from zanni.files.schemas import CastEntry, Part, Pin, covers
from zanni.protocol.card import ActorCardParams


def within(rule: str, ceilings: list[str]) -> bool:
    """A role's path rule is within a part's ceilings if some ceiling covers all of it."""
    return any(covers(c, rule) or (c.endswith("/") and rule.endswith("/") and rule.startswith(c)) for c in ceilings)


def refusal(card: ActorCardParams, entry: CastEntry, part: Part, pin: Pin | None) -> tuple[str, str] | None:
    """The reason and message for refusing this actor for this part, or None if it fits.

    Seat availability (`part-full`, `host-cap`) and the join token (`not-authorised`) are checked by the director
    against its own state, before this.
    """
    role = card.role
    if role.ref != entry.role:
        return "role-mismatch", f"this part is cast for {entry.role}, and the actor plays {role.ref}"
    if pin is not None and role.hash != pin.hash:
        return "hash-mismatch", f"{role.ref} has hash {role.hash}, and play.lock pins {pin.hash}"
    return _ceilings(card, part)


def _ceilings(card: ActorCardParams, part: Part) -> tuple[str, str] | None:
    role = card.role
    for kind, rules, ceilings in (("write", role.needs.stage_write, part.writes),
                                  ("read", role.needs.stage_read, part.reads)):
        if ceilings is None:
            continue
        outside = [r for r in rules if not within(r, ceilings)]
        if outside:
            return "needs-beyond-part", (f"the role asks to {kind} {', '.join(outside)}, beyond the part's "
                                         f"{kind}s: {', '.join(ceilings) or 'nothing'}")
    return None


def refusal_local(card: ActorCardParams, name: str, role_hash: str, part: Part) -> tuple[str, str] | None:
    """For a local cast entry, whose path differs from machine to machine (D36): the role's name and content hash
    must be those of the folder the play names; then the part's ceilings, as for a remote entry."""
    role = card.role
    if role.name != name:
        return "role-mismatch", f"this part is cast for the role {name}, and the actor plays {role.name}"
    if role.hash != role_hash:
        return "hash-mismatch", (f"the actor's {name} has hash {role.hash}, and the play's folder has {role_hash}: "
                                 "they are different versions of the role")
    return _ceilings(card, part)
