"""The stage's MCP server: each token is one seat's permissions, and a revoked one reaches nothing (D31)."""

import asyncio

import httpx
import pytest

from tests.stage_over_mcp import Tokens, served
from zanni.actor.contract import StageError
from zanni.stage import folder_stage
from zanni.engine.stage_mcp import STAGE_TOOLS, remote_stage


@pytest.fixture
def stages(tmp_path):
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec/a.md").write_text("AC1")
    shared = folder_stage(tmp_path)
    return {"tester-token": shared.seat(["spec/"], ["tests/"]), "coder-token": shared.seat(["/"], ["app/"])}


def test_each_token_gets_its_own_seats_permissions(stages):
    with served(stages) as remote:
        tester, coder = remote["tester-token"], remote["coder-token"]
        assert tester.write("tests/t.py", "ok") == "1"
        with pytest.raises(StageError) as refused:
            tester.write("app/x.py", "no")
        assert refused.value.code == "not-permitted"
        assert coder.write("app/x.py", "yes") == "2"  # one record, shared by the play's seats
        assert tester.changes()[0] == [("tests/t.py", "written")]  # a seat sees only changes it may read
        assert coder.changes()[0] == [("tests/t.py", "written"), ("app/x.py", "written")]


def test_a_revoked_token_reaches_nothing(stages):
    with served(stages) as remote:
        tester = remote["tester-token"]
        assert tester.read("spec/a.md") == "AC1"
        remote["tokens"].revoked.add("tester-token")
        with pytest.raises(StageError) as refused:
            tester.read("spec/a.md")
        assert refused.value.code in ("unavailable", "not-authorised")


def test_an_unknown_token_gets_http_401(stages):
    with served(stages) as remote:
        response = httpx.post(remote["url"] + "/stage/mcp", headers={"Authorization": "Bearer someone-elses"},
                              json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert response.status_code == 401

        async def connect():
            async with remote_stage(remote["url"] + "/stage/mcp", "someone-elses") as stage:
                await stage.read("spec/a.md")

        with pytest.raises(StageError) as refused:
            asyncio.run(connect())
        assert refused.value.code == "unavailable"


def test_the_server_offers_exactly_the_five_stage_tools(stages):
    with served(stages) as remote:
        tools = asyncio.run_coroutine_threadsafe(
            remote["tester-token"].remote.client.list_tools(), remote["tester-token"].loop).result(10)
        assert sorted(t.name for t in tools.tools) == sorted(STAGE_TOOLS)
