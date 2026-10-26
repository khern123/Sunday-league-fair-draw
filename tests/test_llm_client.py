import json
import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from fairdraw import llm_client
from fairdraw import usage_log
from fairdraw.env_loader import KeyState


def setup_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(llm_client, "CACHE_FILE", tmp_path / "cache.json")
    monkeypatch.setattr(llm_client, "COUNTER_FILE", tmp_path / "daily.json")
    monkeypatch.setattr(llm_client, "USAGE_FILE", tmp_path / "legacy.json")
    monkeypatch.setattr(llm_client, "append_usage", lambda *args, **kwargs: None)
    monkeypatch.setattr(llm_client, "load_key_state", lambda root=None: KeyState("PORTKEY_API_KEY", "fake", "gpt-6-luna", Path("fake.env"), "API key loaded."))


def fake_response(text="OK", prompt=3, completion=2):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, prompt_tokens_details=SimpleNamespace(cached_tokens=0),
                              total_tokens=prompt + completion),
    )


def test_no_key_raises_specific_error(monkeypatch, tmp_path: Path) -> None:
    setup_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(llm_client, "load_key_state", lambda root=None: KeyState(None, None, None, None, "No API key found."))
    with pytest.raises(llm_client.NoKeyError, match="No API key"):
        llm_client.call_llm([{"role": "user", "content": "OK"}], "command", 5)


def test_cache_hit_skips_model_call(monkeypatch, tmp_path: Path) -> None:
    setup_paths(monkeypatch, tmp_path)
    calls = []

    async def fake_request(*args, **kwargs):
        calls.append(True)
        return fake_response()

    monkeypatch.setattr(llm_client, "_request", fake_request)
    messages = [{"role": "user", "content": "Reply OK"}]
    first = llm_client.call_llm(messages, "command", 5)
    second = llm_client.call_llm(messages, "command", 5)
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert len(calls) == 1


def test_limits_are_enforced_before_model_call(monkeypatch, tmp_path: Path) -> None:
    setup_paths(monkeypatch, tmp_path)
    llm_client._write_json(llm_client.COUNTER_FILE, {"date": str(date.today()), "daily": 0, "session": 0, "run": 99, "process_id": os.getpid()})
    with pytest.raises(llm_client.LLMCallLimitError, match="maximum number"):
        llm_client.call_llm([{"role": "user", "content": "OK"}], "command", 5)


def test_usage_line_is_written_for_a_real_uncached_mock(monkeypatch, tmp_path: Path) -> None:
    setup_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(usage_log, "USAGE_LOG", tmp_path / "usage_log.jsonl")
    monkeypatch.setattr(llm_client, "append_usage", usage_log.append_usage)
    records = []

    async def fake_request(*args, **kwargs):
        return fake_response(prompt=7, completion=4)

    monkeypatch.setattr(llm_client, "_request", fake_request)
    result = llm_client.call_llm([{"role": "user", "content": "Reply OK"}], "command", 5)
    assert result.usage == {"input_tokens": 7, "cached_input_tokens": 0, "output_tokens": 4}
    line = json.loads((tmp_path / "usage_log.jsonl").read_text(encoding="utf-8").strip())
    assert line["purpose"] == "command"
    assert line["model"] == "gpt-6-luna"
    assert line["input_tokens"] == 7
    assert line["cache_hit"] is False
