"""The director's rules in code (D33, D35, D39), the host cap, and a report's changes from the stage's record (D41)."""

import asyncio
from decimal import Decimal

import pytest

from tests.test_director import JOIN_TOKEN, URL, Clock, join_message
from zanni.actor.stage import FolderStage
from zanni.director import rules
from zanni.director.casting import Director, PartSlot
from zanni.director.state import PlayState, Verdict
from zanni.files.schemas import PlayFile, Script
from zanni.log import Log
from zanni.protocol.messages import Cue, Refused, Report


def state(budget=None, gates=(), house_gates=(), done_when=(), max_rounds=None, per_round=None, seats="1-2"):
    script = Script.model_validate({
        "name": "kata", "version": "1.0.0", "mission": "m", "parts": {"coder": {"seats": seats}, "tester": {}},
        "gates": list(gates),
        "verifiers": {"tests-fail": {"description": "new tests fail", "command": ["x"]},
                      "tests-pass": {"description": "tests pass", "command": ["x"]}},
        "stop": {"done_when": list(done_when), "max_rounds": max_rounds, "budget_per_round": per_round}})
    play = PlayFile.model_validate({"name": "p", "script": "./kata", "stage": "./stage",
                                    "cast": {"coder": {"role": "./coder", "host": "local"}, "tester": "./tester"},
                                    "house_rules": {"budget": budget, "gates": list(house_gates)}})
    return PlayState(play, script)


def verdict(name, passed=True, marker=3, round=1):
    return Verdict(name, passed, "", "script", marker, round)


# The budget (D39)

def test_without_a_budget_a_cue_has_none():
    assert rules.cue_budget(state(), idle_seats=2, asked=None) == (None, None)


def test_a_cues_budget_is_the_unreserved_budget_shared_among_idle_seats():
    s = state(budget=Decimal("2.00"))
    assert rules.cue_budget(s, idle_seats=3, asked=None) == (Decimal("0.6666"), None)
    s.spend, s.reservations = Decimal("0.50"), {"c-1": Decimal("0.50")}
    assert rules.cue_budget(s, idle_seats=2, asked=None) == (Decimal("0.5000"), None)


def test_the_model_may_ask_for_less_never_more():
    s = state(budget=Decimal("1.00"))
    assert rules.cue_budget(s, 2, Decimal("0.10")) == (Decimal("0.10"), None)
    budget, refusal = rules.cue_budget(s, 2, Decimal("0.80"))
    assert budget is None and "at most $0.5000" in refusal


def test_nothing_left_to_reserve_is_refused():
    s = state(budget=Decimal("1.00"))
    s.spend, s.reservations = Decimal("0.60"), {"c-1": Decimal("0.40")}
    budget, refusal = rules.cue_budget(s, 1, None)
    assert budget is None and "nothing is left of the budget to reserve" in refusal


def test_the_round_budget_caps_a_cue_too():
    s = state(per_round=Decimal("0.30"))
    assert rules.cue_budget(s, 1, None) == (Decimal("0.3000"), None)
    s.round_spend = Decimal("0.30")
    assert "this round has used its budget" in rules.cue_budget(s, 1, None)[1]


def test_unknown_cost_makes_the_spend_at_least():
    s = state(budget=Decimal("1.00"))
    s.charge(Decimal("0.25"))
    s.charge(None)
    assert s.spend_text() == "at least $0.2500" and s.spend == Decimal("0.25")


def test_the_director_stops_before_a_turn_once_the_budget_is_reached():
    s = state(budget=Decimal("1.00"))
    assert rules.director_may_take_a_turn(s) is None
    s.spend = Decimal("1.00")
    assert rules.director_may_take_a_turn(s) == "budget"


# "Done" (D33, D35)

def test_done_needs_every_enforced_gate_approved():
    s = state(gates=["plan", "release"], house_gates=["plan"], done_when=["tests-pass"])
    s.verdicts["tests-pass"] = verdict("tests-pass")
    assert "plan haven't been approved" in rules.may_stop_done(s, marker=3)
    s.gates["plan"] = "approved"
    assert rules.may_stop_done(s, marker=3) is None  # release isn't enforced by this play


def test_done_needs_done_when_passed_after_the_last_change():
    s = state(done_when=["tests-pass"])
    assert "tests-pass (never run)" in rules.may_stop_done(s, marker=3)
    s.verdicts["tests-pass"] = verdict("tests-pass", passed=False)
    assert "tests-pass (failed)" in rules.may_stop_done(s, marker=3)
    s.verdicts["tests-pass"] = verdict("tests-pass", marker=2)
    assert "the stage changed after it passed" in rules.may_stop_done(s, marker=3)
    s.verdicts["tests-pass"] = verdict("tests-pass", marker=3)
    assert rules.may_stop_done(s, marker=3) is None


def test_not_every_verifier_must_pass_at_the_end():
    s = state(done_when=["tests-pass"])
    s.verdicts["tests-fail"] = verdict("tests-fail", passed=False)
    s.verdicts["tests-pass"] = verdict("tests-pass")
    assert rules.may_stop_done(s, marker=3) is None


def test_without_done_when_a_verifier_must_pass_in_this_round():
    s = state()
    assert "at least one verifier run and passed in this round" in rules.may_stop_done(s, marker=3)
    s.verdicts["tests-pass"] = verdict("tests-pass", round=1)
    assert rules.may_stop_done(s, marker=3) is None
    s.verdicts["tests-fail"] = verdict("tests-fail", passed=False)
    assert "verifiers failed in this round: tests-fail" in rules.may_stop_done(s, marker=3)


# Verifiers, cues, casting, rounds

def test_a_verifier_must_be_the_scripts_and_wait_for_writing_cues():
    s = state()
    assert "no verifier 'lint'" in rules.may_run_verifier(s, "lint", writing_cues=0)
    assert "1 cue(s) that write to the stage are still pending" in rules.may_run_verifier(s, "tests-pass", 1)
    assert rules.may_run_verifier(s, "tests-pass", 0) is None


def test_a_cues_paths_stay_within_its_seat():
    assert rules.paths_within(["spec/"], ["tests/"], reads=["spec/a.md", "tests/"], writes=["tests/test_a.py"]) is None
    assert "may not write app/x.py" in rules.paths_within(["spec/"], ["tests/"], reads=[], writes=["app/x.py"])
    assert "may not read vision.md" in rules.paths_within(["spec/"], ["tests/"], reads=["vision.md"], writes=[])


def test_the_stage_must_hold_what_the_script_expects(tmp_path):
    (tmp_path / "vision.md").write_text("v")
    assert rules.stage_missing(tmp_path, ["vision.md", "backlog/"]) == ["backlog/"]


def test_casting_stays_within_the_seats_and_the_local_files():
    s = state(seats="1-2")
    assert "may have 1-2 seat(s); 3 is outside that" in rules.may_cast(s, "coder", 3, 1, 2, 1, has_remote=False)
    assert rules.may_cast(s, "coder", 2, 1, 2, 1, has_remote=False) is None
    assert "every local seat listed for coder is already started" in rules.may_cast(s, "coder", 2, 1, 1, 1, False)
    assert rules.may_cast(s, "coder", 2, 1, 1, 1, has_remote=True) is None
    assert "no part 'editor'" in rules.may_cast(s, "editor", 1, 0, 0, 0, True)


def test_rounds_stop_at_max_rounds():
    s = state(max_rounds=2)
    assert rules.may_end_round(s) is None
    s.round = 2
    assert rules.may_end_round(s) == "max-rounds"


# The host cap, and changes per seat (D41)

def two_seats(tmp_path, max_per_host=None):
    (tmp_path / "stage").mkdir(exist_ok=True)
    clock = Clock()
    return Director(join_token=JOIN_TOKEN, parts=[PartSlot("tester", lambda p: None, 3)],
                    stage=FolderStage(tmp_path / "stage", [], []), log=Log(tmp_path / "log.jsonl", "r1"),
                    clock=lambda: clock.t, utcnow=lambda: clock.utc, max_per_host=max_per_host)


def test_the_host_cap_counts_seats_by_the_address_they_joined_from(tmp_path):
    async def go():
        d = two_seats(tmp_path, max_per_host=1)
        first = await d.join(JOIN_TOKEN, "t1", join_message(), None, URL, peer="10.0.0.5")
        second = await d.join(JOIN_TOKEN, "t2", join_message(), None, URL, peer="10.0.0.5")
        third = await d.join(JOIN_TOKEN, "t3", join_message(), None, URL, peer="10.0.0.6")
        return first, second, third

    first, second, third = asyncio.run(go())
    assert not isinstance(first, Refused) and not isinstance(third, Refused)
    assert second.reason == "host-cap" and "1 per host" in second.message


def test_a_report_holds_only_its_own_seats_changes(tmp_path):
    async def go():
        d = two_seats(tmp_path)
        await d.join(JOIN_TOKEN, "t1", join_message(), None, URL)
        await d.join(JOIN_TOKEN, "t2", join_message(), None, URL)
        a, b = d.seats["t1"], d.seats["t2"]
        a.stage.write_rules, b.stage.write_rules = ["/"], ["/"]
        cue = lambda n: Cue(kind="zanni.cue", cue=f"c-{n}", scene="s", instructions="i")  # noqa: E731
        wa, wb = asyncio.create_task(d.cue(a, cue(1))), asyncio.create_task(d.cue(b, cue(2)))
        await asyncio.sleep(0)
        a.stage.write("a.txt", "a")
        b.stage.write("b.txt", "b")
        a.stage.write("a2.txt", "a")
        claimed = ["1", "2", "3"]  # the actor sees every change; the director knows better
        await d.report("t1", Report(kind="zanni.report", cue="c-1", outcome="done", summary="", changes=claimed, cost=None))
        await d.report("t2", Report(kind="zanni.report", cue="c-2", outcome="done", summary="", changes=claimed, cost=None))
        return await wa, await wb

    ra, rb = asyncio.run(go())
    assert ra.changes == ["1", "3"] and rb.changes == ["2"]


@pytest.mark.parametrize("since,expected", [(0, ["1", "3"]), (1, ["3"]), (3, [])])
def test_made_by_counts_from_a_marker(tmp_path, since, expected):
    stage = FolderStage(tmp_path, [], ["/"], who="a")
    other = stage.seat([], ["/"], who="b")
    stage.write("x", "1")
    other.write("y", "2")
    stage.write("z", "3")
    assert stage.made_by("a", since) == expected
