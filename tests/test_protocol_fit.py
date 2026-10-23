from zanni.files.schemas import CastEntry, Part, Pin
from zanni.protocol.card import ActorCardParams

H1 = "sha256:" + "1" * 64
H2 = "sha256:" + "2" * 64


def card(ref="roles/tester", hash=H1, write=("tests/",), read=()):
    return ActorCardParams(role={"ref": ref, "hash": hash, "name": "tester", "version": "1.0.0",
                                 "needs": {"stage_write": list(write), "stage_read": list(read)}})


ENTRY = CastEntry(role="roles/tester")
PART = Part(writes=["tests/", "findings/"])


def refusal(c, part=PART, pin=None):
    from zanni.protocol.fit import refusal as r
    return r(c, ENTRY, part, pin)


def test_a_fitting_actor_is_not_refused():
    assert refusal(card(write=["tests/", "findings/report.md"])) is None


def test_role_mismatch():
    assert refusal(card(ref="roles/coder"))[0] == "role-mismatch"


def test_hash_mismatch_against_the_lockfile():
    assert refusal(card(), pin=Pin(hash=H2))[0] == "hash-mismatch"
    assert refusal(card(), pin=Pin(hash=H1)) is None


def test_needs_beyond_the_parts_ceilings():
    reason, message = refusal(card(write=["app/"]))
    assert reason == "needs-beyond-part"
    assert "the role asks to write app/, beyond the part's writes: tests/, findings/" == message


def test_no_ceiling_means_the_roles_needs_apply():
    assert refusal(card(write=["anything/"]), part=Part()) is None
