"""Gates and pauses (D33, D38): the play waits until a person decides, from outside the director.

A gate (or a pause, when every one of the director's models failed) is a state of the play. `decide` is called by
the owner's endpoint (`zanni gate`), or by the console when the director runs in a terminal; never by an actor.
"""

import asyncio
from dataclasses import dataclass

from zanni.director.state import PlayState
from zanni.log import Log


@dataclass(frozen=True)
class Decision:
    action: str  # approve, reject or resume; "timeout" when gate_timeout passed first
    note: str = ""
    by: str = ""


class Gates:
    def __init__(self, state: PlayState, log: Log, timeout: int | None, say=print):
        self.state, self.log, self.timeout, self.say = state, log, timeout, say
        self._waiting: asyncio.Future | None = None
        self.changed = asyncio.Event()  # set whenever a gate or pause starts or ends (for the console prompt)

    @property
    def state_name(self) -> str:
        if self.state.stopped:
            return "stopped"
        if self.state.pending_gate:
            return "gate"
        return "paused" if self.state.paused else "running"

    async def _wait(self) -> Decision:
        self._waiting = asyncio.get_running_loop().create_future()
        self.changed.set()
        try:
            return await asyncio.wait_for(asyncio.shield(self._waiting), self.timeout)
        except TimeoutError:
            return Decision("timeout")
        finally:
            self._waiting = None
            self.changed.set()

    async def gate(self, name: str, summary: str) -> Decision:
        """Pause at a gate the play enforces, until approve, reject, or gate_timeout."""
        self.state.pending_gate = (name, summary)
        self.log.event("gate-pending", gate=name, summary=summary)
        self.say(f"Gate '{name}' is waiting for a decision: zanni gate <play> approve | reject --note …")
        try:
            decision = await self._wait()
        finally:
            self.state.pending_gate = None
        if decision.action == "timeout":
            self.log.event("gate", gate=name, decision="timeout", by=None, note=None)
        else:
            outcome = "approved" if decision.action == "approve" else "rejected"
            self.state.gates[name] = outcome
            self.log.event("gate", gate=name, decision=outcome, by=decision.by, note=decision.note)
            self.say(f"Gate '{name}' {outcome}{' by ' + decision.by if decision.by else ''}"
                     f"{': ' + decision.note if decision.note else ''}")
        return decision

    async def pause(self, reason: str) -> Decision:
        """Every director model failed: wait until the owner resumes the play, or gate_timeout (D33)."""
        self.state.paused = reason
        self.log.event("paused", reason=reason)
        self.say(f"Paused: {reason}. Resume with: zanni gate <play> resume")
        try:
            decision = await self._wait()
        finally:
            self.state.paused = None
        if decision.action == "resume":
            self.log.event("resumed", by=decision.by, note=decision.note)
            self.say("Resumed.")
        return decision

    def decide(self, action: str, note: str = "", by: str = "owner") -> str | None:
        """A person's decision. None when it was taken; otherwise why it can't be, in plain words."""
        if self._waiting is None or self._waiting.done():
            return "nothing is waiting for a decision: no gate is pending and the play isn't paused"
        if action in ("approve", "reject") and not self.state.pending_gate:
            return "the play is paused, not at a gate; use resume"
        if action == "resume" and not self.state.paused:
            return "the play is at a gate, not paused; use approve or reject"
        if action == "reject" and not note.strip():
            return "a rejection needs a note saying what to change"
        if action not in ("approve", "reject", "resume"):
            return f"{action!r} isn't a decision; use approve, reject or resume"
        self._waiting.set_result(Decision(action, note, by))
        return None
