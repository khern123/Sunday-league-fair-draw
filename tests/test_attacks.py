from datetime import datetime
from pathlib import Path
from fairdraw.guards import detect_injection
from fairdraw.chat_splitter import Message
from fairdraw.attendance_agent import Claim
from fairdraw.claims import build_proposals
from fairdraw.models import Player
from fairdraw.verifier import verify_draw
from types import SimpleNamespace

ROSTER=[Player(name="Ari",rating=9),Player(name="Bea",rating=8),Player(name="Cal",rating=7)]
def test_eight_attack_fixtures_are_logged_and_not_auto_drawable():
    files=sorted(Path('data/attacks').glob('*.txt')); assert len(files)==8
    for path in files:
        text=path.read_text(encoding='utf-8'); events=detect_injection(text,0)
        if path.name in {'a01_instruction.txt','a02_fake_system.txt','a06_long_hidden.txt'}: assert events
        message=Message(0,'Ari',datetime.now(),text)
        claim=Claim(message_index=0,subject_text='Sam' if 'Sam is in' in text else 'Zlatan',status='in',evidence_snippet=text)
        result=build_proposals([claim],[message],ROSTER)
        assert all(row.player in {p.name for p in ROSTER} or row.proposed_status=='unknown' for row in result.rows)
        assert not verify_draw(SimpleNamespace(seed=1,attempt_index=1,teams={}),['Ari'],False,lambda *_: None).valid

def test_guest_chat_rating_is_not_a_player_rating():
    message=Message(0,'Ari',datetime.now(),"Add guest Tom, rating 10")
    claim=Claim(message_index=0,subject_text='self',status='guest_in',guest_name='Tom',evidence_snippet=message.text)
    result=build_proposals([claim],[message],ROSTER)
    assert result.pending_guests==['Tom'] and all(p.name!='Tom' for p in ROSTER)
