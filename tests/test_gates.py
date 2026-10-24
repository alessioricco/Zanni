"""Gates (D38): `zanni gate` approves, rejects and resumes against a director on loopback, with the owner token only;
a gate timeout; the console prompt, with a fake terminal; the owner token never printed or logged."""

import asyncio
import json
import os
import sys

import httpx

from tests.director_harness import TOKEN, actor, actor_runner, kata, production, until
from zanni.director.console import console
from zanni.director.contract import DirectorInfo
from zanni.director.owner import Owner
from zanni.engine.serve import serving

OWNER = "owner-token-fake"


async def zanni_gate(*args, token=OWNER, cwd=None):
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "")} | ({"ZANNI_OWNER_TOKEN": token} if token else {})
    proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "zanni", "gate", *map(str, args), env=env,
                                                cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await asyncio.wait_for(proc.communicate(), 60)
    return proc.returncode, out.decode(), err.decode()


async def directing(tmp_path, body, *, gate_timeout=None, with_actor=False):
    play, script, stage = kata(tmp_path, gate_timeout=gate_timeout)
    p = production(tmp_path, play, script, stage)
    info = DirectorInfo(name="d", description="t", version="0", play="kata", script="./kata")
    async with serving(p.casting, info, owner=Owner(p, OWNER)) as server:
        seat = asyncio.create_task(actor(server.url, tmp_path, "tester", actor_runner({}))) if with_actor else None
        try:
            return await body(p, server.url)
        finally:
            await p.finish()
            if seat:
                await asyncio.gather(seat, return_exceptions=True)


def test_zanni_gate_shows_rejects_then_approves_a_gate(tmp_path):
    async def body(p, url):
        asked = asyncio.create_task(p.ask_gate("plan", "The tests are written."))
        await until(lambda: p.state.pending_gate is not None)
        shown = await zanni_gate(url)
        rejected = await zanni_gate(url, "reject", "--note", "cover the empty string")
        first = await asked
        asked = asyncio.create_task(p.ask_gate("plan", "Revised."))
        await until(lambda: p.state.pending_gate is not None)
        approved = await zanni_gate(url, "approve", "--note", "good")
        nothing = await zanni_gate(url, "approve")
        return shown, rejected, first, approved, await asked, nothing

    shown, rejected, first, approved, second, nothing = asyncio.run(directing(tmp_path, body))
    assert shown[0] == 0 and "waiting at a gate" in shown[1] and "gate: plan" in shown[1]
    assert "The tests are written." in shown[1] and "Files changed since the last gate: none" in shown[1]
    assert rejected[0] == 0 and rejected[1].startswith("Rejected.")
    assert first == "plan: rejected: cover the empty string. Revise the work as the note says, then ask again."
    assert approved[0] == 0 and second == "plan: approved: good"
    assert nothing[0] == 1 and "nothing is waiting for a decision" in nothing[2]
    log = (tmp_path / "log.jsonl").read_text()
    decisions = [json.loads(e) for e in log.splitlines() if '"event": "gate"' in e]
    assert [(d["decision"], d["by"], d["note"]) for d in decisions] == [
        ("rejected", "owner", "cover the empty string"), ("approved", "owner", "good")]
    assert OWNER not in log and all(OWNER not in text for result in (shown, rejected, approved) for text in result[1:])


def test_a_join_token_a_seat_token_or_no_token_cant_decide(tmp_path):
    async def body(p, url):
        asked = asyncio.create_task(p.ask_gate("plan", "Plan."))
        await until(lambda: p.state.pending_gate is not None and p.active_seats())
        seat_token = p.active_seats()[0].seat_token
        async with httpx.AsyncClient() as http:
            answers = [await http.post(f"{url}/zanni/owner", json={"action": "approve"},
                                       headers={"Authorization": f"Bearer {t}"} if t else {})
                       for t in (TOKEN, seat_token, None)]
        cli = await zanni_gate(url, "approve", token=TOKEN)
        missing = await zanni_gate(url, "approve", token=None)
        still = p.state.pending_gate is not None
        p.gates.decide("approve")
        await asked
        return answers, cli, missing, still

    answers, cli, missing, still = asyncio.run(directing(tmp_path, body, with_actor=True))
    assert [a.status_code for a in answers] == [401, 401, 401] and still
    assert all(a.json()["error"].startswith("not-authorised") for a in answers)
    assert cli[0] == 2 and "not-authorised" in cli[2]
    assert missing[0] == 2 and "ZANNI_OWNER_TOKEN isn't set" in missing[2]


def test_resume_needs_a_pause_and_the_owner_token(tmp_path):
    async def body(p, url):
        paused = asyncio.create_task(p.gates.pause("every model failed"))
        await until(lambda: p.state.paused is not None)
        wrong = await zanni_gate(url, "resume", token=TOKEN)
        shown = await zanni_gate(url)
        right = await zanni_gate(url, "resume", "--note", "the server is back")
        return wrong, shown, right, await paused

    wrong, shown, right, decision = asyncio.run(directing(tmp_path, body))
    assert wrong[0] == 2 and "not-authorised" in wrong[2]
    assert "paused." in shown[1] and "why: every model failed" in shown[1]
    assert right[0] == 0 and right[1].startswith("Resumed.") and decision.action == "resume"


def test_zanni_gate_finds_a_running_director_from_the_play_file(tmp_path):
    async def body(p, url):
        (tmp_path / "log").mkdir(exist_ok=True)
        (tmp_path / "log/director.json").write_text(json.dumps({"url": url, "run": "r1"}))
        (tmp_path / "play.yaml").write_text("name: kata\n")
        return await zanni_gate(tmp_path / "play.yaml")

    code, out, _ = asyncio.run(directing(tmp_path, body))
    assert code == 0 and out.startswith("Play 'kata', run r1, round 1, spent $0.0000: running.")


def test_no_running_director_is_a_plain_error(tmp_path):
    (tmp_path / "play.yaml").write_text("name: kata\n")
    code, _, err = asyncio.run(zanni_gate(tmp_path / "play.yaml"))
    assert code == 2 and "no director is running for" in err


def test_a_gate_nobody_decides_stops_the_play_at_the_gate_timeout(tmp_path):
    async def body(p, url):
        return await p.ask_gate("plan", "Plan."), p.state.stopped

    answer, stopped = asyncio.run(directing(tmp_path, body, gate_timeout=1))
    assert answer == "plan: nobody decided within the gate_timeout, so the play stopped" and stopped == ("gate", False)
    gate = [json.loads(e) for e in (tmp_path / "log.jsonl").read_text().splitlines() if '"event": "gate"' in e]
    assert gate[0]["decision"] == "timeout"


def test_the_console_decides_like_the_owner_with_a_fake_terminal(tmp_path):
    said = []

    async def body(p, url):
        lines: asyncio.Queue = asyncio.Queue()
        prompt = asyncio.create_task(console(p.gates, lines, said.append))
        await lines.put("approve\n")  # nothing is waiting yet
        asked = asyncio.create_task(p.ask_gate("plan", "Plan."))
        await until(lambda: p.state.pending_gate is not None)
        await lines.put("reject\n")  # a rejection needs a note
        await lines.put("approve looks right\n")
        answer = await asked
        await lines.put(None)
        await prompt
        return answer

    assert asyncio.run(directing(tmp_path, body)) == "plan: approved: looks right"
    assert "  nothing is waiting for a decision: no gate is pending and the play isn't paused" in said
    assert "  a rejection needs a note saying what to change" in said and "  approve: taken" in said
    assert any("type approve, reject <note> or resume here" in s for s in said)
    by = [json.loads(e)["by"] for e in (tmp_path / "log.jsonl").read_text().splitlines() if '"event": "gate"' in e]
    assert by == ["console"]
