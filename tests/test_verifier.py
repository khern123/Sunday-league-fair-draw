from datetime import datetime
from types import SimpleNamespace

from fairdraw.attendance_agent import Claim
from fairdraw.chat_splitter import Message
from fairdraw.verifier import verify_announcement, verify_claims, verify_draw


def test_claim_verifier_requires_exact_evidence_and_message():
    messages = [Message(0, "Sam", datetime.now(), "Sam is in")]
    good = Claim(message_index=0, subject_text="Sam", status="in", evidence_snippet="Sam is in")
    bad = Claim(message_index=9, subject_text="Sam", status="in", evidence_snippet="Sam is in")
    result = verify_claims([good, bad], messages)
    assert result.claims == [good] and result.events[0].type == "claim_dropped"


def test_draw_verifier_replays_seed_and_requires_confirmation():
    result = SimpleNamespace(seed=42, attempt_index=1, teams={"A": ["Sam"], "B": ["Alex"]})
    replay = lambda seed, attempt: result
    assert verify_draw(result, ["Sam", "Alex"], True, replay).valid
    assert not verify_draw(result, ["Sam", "Alex"], False, replay).valid


def test_announcement_verifier_rejects_unknown_names_and_numbers():
    assert verify_announcement("Team A: Sam\nDraw #1, seed 42", ["Sam"], ["Team A"], [1, 42]).valid
    assert not verify_announcement("Team A: Hacker\nDraw #1, seed 999", ["Sam"], ["Team A"], [1, 42]).valid
