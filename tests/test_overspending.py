from datetime import date
import os
import pytest
from fairdraw import llm_client
from fairdraw.env_loader import KeyState

def test_per_run_budget_blocks_before_model(monkeypatch,tmp_path):
    monkeypatch.setattr(llm_client,'CACHE_FILE',tmp_path/'cache.json'); monkeypatch.setattr(llm_client,'COUNTER_FILE',tmp_path/'daily.json'); monkeypatch.setattr(llm_client,'USAGE_FILE',tmp_path/'legacy.json'); monkeypatch.setattr(llm_client,'append_usage',lambda *a,**k:None); monkeypatch.setattr(llm_client,'load_key_state',lambda root=None:KeyState('PORTKEY_API_KEY','fake','gpt-6-luna',None,'ok'))
    llm_client._write_json(llm_client.COUNTER_FILE,{'date':str(date.today()),'daily':0,'session':0,'run':llm_client.config.MAX_LLM_CALLS_PER_RUN,'process_id':os.getpid()})
    with pytest.raises(llm_client.LLMCallLimitError): llm_client.call_llm([{'role':'user','content':'x'}],'command',5)

def test_cache_repeat_uses_zero_tokens(monkeypatch,tmp_path):
    monkeypatch.setattr(llm_client,'CACHE_FILE',tmp_path/'cache.json'); monkeypatch.setattr(llm_client,'COUNTER_FILE',tmp_path/'daily.json'); monkeypatch.setattr(llm_client,'USAGE_FILE',tmp_path/'legacy.json'); monkeypatch.setattr(llm_client,'append_usage',lambda *a,**k:None); monkeypatch.setattr(llm_client,'load_key_state',lambda root=None:KeyState('PORTKEY_API_KEY','fake','gpt-6-luna',None,'ok'))
    async def fake(*a,**k): return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"actions":[]}'))],usage=SimpleNamespace(prompt_tokens=1,completion_tokens=1,prompt_tokens_details=SimpleNamespace(cached_tokens=0)))
    from types import SimpleNamespace
    monkeypatch.setattr(llm_client,'_request',fake); messages=[{'role':'user','content':'x'}]; llm_client.call_llm(messages,'command',5); second=llm_client.call_llm(messages,'command',5); assert second.cache_hit and second.usage['input_tokens']==0
