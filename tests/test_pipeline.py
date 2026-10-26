from datetime import datetime
from pathlib import Path

from fairdraw.attendance_agent import Claim, AttendanceResult
from fairdraw.models import Player
from fairdraw import pipeline


def test_pipeline_with_mocked_llm(monkeypatch):
    roster = [Player(name="Ari", rating=9), Player(name="Bea", rating=8), Player(name="Cal", rating=7)]

    def fake_extract(messages, roster_names, aliases, batch_size=25):
        return AttendanceResult(
            [Claim(message_index=0, subject_text="self", status="in", evidence_snippet="I'm in tonight")], []
        )

    monkeypatch.setattr(pipeline, "extract_attendance", fake_extract)
    result = pipeline.run_attendance_pipeline("10/25/26, 14:02 - Ari: I'm in tonight", roster)
    assert result["messages"][0].sender == "Ari"
    assert result["proposed_attendance"][0].player == "Ari"
    assert result["token_totals"]["calls"] == 0
