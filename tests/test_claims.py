from datetime import datetime

from fairdraw.attendance_agent import Claim
from fairdraw.chat_splitter import Message
from fairdraw.claims import build_proposals
from fairdraw.models import Player


ROSTER = [Player(name="Sam", rating=7, aliases=["Samuel"]), Player(name="Alex", rating=6)]


def msg(index, sender, text, minute):
    return Message(index, sender, datetime(2026, 10, 25, 14, minute), text)


def claim(index, subject, status, evidence, guest_name=None):
    return Claim(message_index=index, subject_text=subject, status=status, evidence_snippet=evidence, guest_name=guest_name)


def test_self_claim_latest_edit_wins():
    messages = [msg(0, "Sam", "I'm in", 1), msg(1, "Sam", "actually I can't make it", 2)]
    result = build_proposals([claim(0, "self", "in", "I'm in"), claim(1, "self", "out", "actually I can't make it")], messages, ROSTER)
    assert [(row.player, row.proposed_status) for row in result.rows] == [("Sam", "out")]


def test_alias_and_case_insensitive_self_resolution():
    result = build_proposals([claim(0, "self", "in", "I'm in")], [msg(0, "sam", "I'm in", 1)], ROSTER)
    assert result.rows[0].player == "Sam" and result.rows[0].source == "self claim"


def test_third_party_needs_confirmation():
    result = build_proposals([claim(0, "Samuel", "out", "Sam is out")], [msg(0, "Alex", "Sam is out", 1)], ROSTER)
    assert result.rows[0].flag == "needs confirmation" and result.rows[0].source == "third-party"
    assert result.defense_events[0].event == "third_party_confirmation"


def test_mass_claim_rejected():
    result = build_proposals([claim(0, "self", "in", "I'm in for everyone")], [msg(0, "Sam", "I'm in for everyone", 1)], ROSTER)
    assert not result.rows and result.defense_events[0].event == "rejected_mass_claim"


def test_unknown_name_is_flagged_not_added():
    result = build_proposals([claim(0, "Taylor", "in", "Taylor is in")], [msg(0, "Alex", "Taylor is in", 1)], ROSTER)
    assert result.rows[0].proposed_status == "unknown" and result.rows[0].player is None


def test_guest_pending_has_no_rating():
    result = build_proposals([claim(0, "self", "guest_in", "bringing my friend Tom", "Tom")], [msg(0, "Alex", "bringing my friend Tom", 1)], ROSTER)
    assert result.pending_guests == ["Tom"] and result.rows[0].source == "guest" and result.rows[0].guest_name == "Tom"


def test_maybe_and_late_are_code_mapped():
    messages = [msg(0, "Sam", "probably in", 1), msg(1, "Alex", "I'll be late", 2)]
    result = build_proposals([claim(0, "self", "maybe", "probably in"), claim(1, "self", "late", "I'll be late")], messages, ROSTER)
    assert [(row.player, row.proposed_status, row.flag) for row in result.rows] == [("Sam", "maybe", None), ("Alex", "in", "late")]
