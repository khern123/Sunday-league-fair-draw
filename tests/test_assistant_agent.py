from types import SimpleNamespace
import pytest
from fairdraw import assistant_agent

def mocked(monkeypatch, payload):
    monkeypatch.setattr(assistant_agent,'call_llm',lambda *a,**k:SimpleNamespace(output=payload))

def test_valid_plan_executes_and_pauses_mutations(monkeypatch):
    mocked(monkeypatch,{"calls":[{"tool":"set_status","player":"sam","status":"late","chat_text":None,"name":None,"num_teams":None,"seed_mode":None,"note":None},{"tool":"run_draw","player":None,"status":None,"chat_text":None,"name":None,"num_teams":2,"seed_mode":"Automatic","note":None}]})
    plan=assistant_agent.validate_plan(assistant_agent.plan_request('mark Sam late and redraw'),['Sam'])
    results,trace=assistant_agent.execute_plan(plan,{'set_status':lambda **x:'set'},approve=lambda call:False)
    assert len(results)==1 and trace[-1]['status']=='blocked'

def test_rating_roster_and_unknown_tools_rejected(monkeypatch):
    mocked(monkeypatch,{"calls":[{"tool":"set_rating","player":"Sam","status":None,"chat_text":None,"name":None,"num_teams":None,"seed_mode":None,"note":None},{"tool":"edit_roster","player":None,"status":None,"chat_text":None,"name":"Sam","num_teams":None,"seed_mode":None,"note":None},{"tool":"send_email","player":None,"status":None,"chat_text":None,"name":None,"num_teams":None,"seed_mode":None,"note":None}]})
    plan=assistant_agent.validate_plan(assistant_agent.plan_request('change rating and roster'),['Sam'])
    assert plan.calls==[] and len(plan.rejected)==3

def test_twenty_calls_rejected(monkeypatch):
    calls=[{"tool":"verify_draw","chat_text":None,"player":None,"status":None,"name":None,"num_teams":None,"seed_mode":None,"note":None} for _ in range(20)]
    result=assistant_agent.validate_plan(assistant_agent.ToolPlan(calls=calls),[])
    assert result.calls==[] and result.rejected
