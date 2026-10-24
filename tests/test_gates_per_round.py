"""Gates every round, and before a part's cues (D48): code refuses a cue, end_round and "done" while the gate isn't
approved as its rhythm requires; a once-per-play gate stays approved; a rejection stands; a gate the play doesn't
enforce never blocks."""

import asyncio

from tests.director_harness import kata, production
from zanni.director import rules
from zanni.director.state import PlayState
from zanni.files.schemas import PlayFile, Script

GATES = [{"name": "plan", "every": "round", "before": ["coder"]}, "release"]


def state(enforced=("plan", "release")) -> PlayState:
    script = Script.model_validate({
        "name": "k", "version": "1.0.0", "mission": "m", "gates": GATES,
        "parts": {"tester": {"writes": ["tests/"]}, "coder": {"writes": ["app/"]}}})
    play = PlayFile.model_validate({"name": "p", "script": "./k", "stage": "./s",
                                    "cast": {"tester": "./t", "coder": "./c"}, "house_rules": {"gates": list(enforced)}})
    return PlayState(play, script)


def approve(s: PlayState, gate: str) -> None:
    s.gates[gate], s.gate_rounds[gate] = "approved", s.round


def test_a_cue_to_a_before_part_waits_for_the_gate_in_this_round():
    s = state()
    assert rules.gates_before(s, "tester") is None  # the tester writes the plan
    assert "plan must be approved in this round before coder gets a cue" in rules.gates_before(s, "coder")
    approve(s, "plan")
    assert rules.gates_before(s, "coder") is None
    s.round = 2  # the next round needs the plan approved again
    assert rules.gates_before(s, "coder") is not None


def test_end_round_and_done_wait_for_an_every_round_gate():
    s = state()
    assert "plan haven't been approved in this round" in rules.round_gates(s)
    approve(s, "plan")
    assert rules.round_gates(s) is None
    approve(s, "release")
    assert "verifier" in (rules.may_stop_done(s, 0) or "")  # past the gates: only the verifiers are missing now
    s.round = 2
    assert "plan" in rules.round_gates(s) and "plan" in rules.may_stop_done(s, 0)


def test_a_once_per_play_gate_stays_approved_and_a_rejection_stands():
    s = state()
    approve(s, "release")
    s.round = 3
    assert s.gate_open("release")
    s.gates["plan"], s.gate_rounds["plan"] = "rejected", 3
    assert not s.gate_open("plan") and rules.gates_before(s, "coder") is not None


def test_a_gate_the_play_doesnt_enforce_never_blocks():
    s = state(enforced=("release",))
    assert rules.gates_before(s, "coder") is None and rules.round_gates(s) is None


def test_the_cue_tool_refuses_a_coder_before_the_rounds_plan(tmp_path):
    play, script, stage = kata(tmp_path, gates=("plan",))
    script = script.model_copy(update={"gates": Script.model_validate({
        "name": "k", "version": "1.0.0", "mission": "m", "parts": {"coder": {}},
        "gates": [{"name": "plan", "every": "round", "before": ["coder"]}]}).gates})
    p = production(tmp_path, play, script, stage)

    class Seat:  # a cast coder, as the casting side would hold it
        id, part, active, verifier, actor = "coder-1", "coder", True, False, "coder-1"
        stage = p.stage.seat(["/"], ["app/"], "coder-1")

    p.casting.seats["t1"] = Seat()
    refusal = asyncio.run(p.cue("coder", "Build", "Write app/slug.py.", writes=["app/"]))
    assert refusal.startswith("refused: the gate(s) plan must be approved in this round before coder")
    summary = p.summary()
    assert "plan (every round, before coder: not asked yet)" in summary
