from types import SimpleNamespace
from fairdraw import assistant_agent
from fairdraw.verifier import verify_announcement

def test_invalid_plan_is_rejected_without_loop(monkeypatch):
    calls=[]
    monkeypatch.setattr(assistant_agent,'call_llm',lambda *a,**k:(calls.append(1) or SimpleNamespace(output='not json')))
    try: assistant_agent.plan_request('do anything')
    except Exception: pass
    assert len(calls)==1

def test_announcement_wrong_name_is_blocked():
    result=verify_announcement('Team A: Invented Player Draw #1 seed 2',['Ari'],['Team A'],[1,2])
    assert not result.valid

def test_invented_claim_player_is_not_accepted():
    from fairdraw.claims import build_proposals
    from fairdraw.attendance_agent import Claim
    from fairdraw.chat_splitter import Message
    from datetime import datetime
    result=build_proposals([Claim(message_index=0,subject_text='Invented',status='in',evidence_snippet='Invented is in')],[Message(0,'Ari',datetime.now(),'Invented is in')],[])
    assert result.rows[0].proposed_status=='unknown'
