"""The play's owner (D38): a person who decides gates and resumes a paused play, from anywhere, with the owner token.

The engine serves this at `/zanni/owner` beside A2A (docs/spec/casting-extension.md, "The owner's endpoint"); this
module decides who may call it and what a call does. The owner token is never printed or logged.
"""

import secrets

from zanni.director.play import Production


class Owner:
    def __init__(self, production: Production, token: str):
        self.production, self.token = production, token

    def authorise(self, token: str | None) -> str | None:
        """None for the play's owner token; otherwise what is wrong. A join or seat token is not an owner's."""
        if not token or not secrets.compare_digest(token, self.token):
            return "not-authorised: this needs the play's owner token (ZANNI_OWNER_TOKEN), not a join or seat token"
        return None

    def status(self) -> dict:
        p = self.production
        s = p.state
        return {"play": s.play.name, "run": p.log.run_id, "state": p.gates.state_name,
                "gate": {"name": s.pending_gate[0], "summary": s.pending_gate[1]} if s.pending_gate else None,
                "paused": {"reason": s.paused} if s.paused else None,
                "round": s.round, "spend": s.spend_text().replace("$", "")}

    def decide(self, action: str, note: str = "", by: str = "owner") -> tuple[int, dict]:
        """(HTTP status, body): 200 with the new state, or 409 when there is nothing to decide, in plain words."""
        problem = self.production.gates.decide(action, note, by)
        if problem:
            return 409, {"error": problem, **self.status()}
        # The play moves on as soon as the decision is taken: it no longer waits.
        return 200, {**self.status(), "state": "running", "gate": None, "paused": None, "decided": action}
