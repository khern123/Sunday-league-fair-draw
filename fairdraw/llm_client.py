"""Single, guarded model-call gateway for all application agents."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from . import config
from .env_loader import load_key_state
from .usage_log import append_usage


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CACHE_FILE = RESULTS / "cache.json"
USAGE_FILE = RESULTS / "usage_log.json"
COUNTER_FILE = RESULTS / "daily_calls.json"
PROMPT_VERSION = "stage4a-v1"
VALID_PURPOSES = {"attendance_parse", "announcement", "command"}
_RAW_USAGE_PRINTED = False


class NoKeyError(RuntimeError):
    """Raised when neither allowed API key is available."""


class LLMCallLimitError(RuntimeError):
    """Raised before a configured call budget would be exceeded."""


@dataclass(frozen=True)
class LLMResponse:
    output: object
    usage: dict[str, int]
    cache_hit: bool


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _input_text(messages) -> str:
    return json.dumps(messages, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _cache_key(purpose: str, messages, model: str) -> str:
    material = f"{purpose}\n{_input_text(messages)}\n{model}\n{PROMPT_VERSION}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _check_limits() -> None:
    counters = _read_json(COUNTER_FILE, {"date": str(date.today()), "daily": 0, "session": 0, "run": 0})
    if counters.get("date") != str(date.today()):
        counters = {"date": str(date.today()), "daily": 0, "session": 0, "run": 0}
    if counters.get("process_id") != os.getpid():
        counters["run"] = 0
        counters["process_id"] = os.getpid()
        _write_json(COUNTER_FILE, counters)
    if counters["run"] >= config.MAX_LLM_CALLS_PER_RUN:
        raise LLMCallLimitError("The maximum number of AI calls for this run has been reached.")
    if counters["session"] >= config.SESSION_CALL_BUDGET:
        raise LLMCallLimitError("The session AI call budget has been reached.")
    if counters["daily"] >= config.DAILY_CALL_BUDGET:
        raise LLMCallLimitError("The daily AI call budget has been reached.")


def _record_call(cache_hit: bool, usage: dict[str, int]) -> None:
    if cache_hit:
        _append_usage({"cache_hit": True, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0})
        return
    counters = _read_json(COUNTER_FILE, {"date": str(date.today()), "daily": 0, "session": 0, "run": 0})
    if counters.get("date") != str(date.today()):
        counters = {"date": str(date.today()), "daily": 0, "session": 0, "run": 0}
    if counters.get("process_id") != os.getpid():
        counters["run"] = 0
        counters["process_id"] = os.getpid()
    counters["daily"] += 1
    counters["session"] += 1
    counters["run"] += 1
    counters["process_id"] = os.getpid()
    _write_json(COUNTER_FILE, counters)
    _append_usage({"cache_hit": False, **usage})


def _append_usage(entry: dict) -> None:
    entries = _read_json(USAGE_FILE, [])
    entries.append(entry)
    _write_json(USAGE_FILE, entries)


async def _request(client: AsyncOpenAI, messages, max_output_tokens: int, json_schema):
    kwargs = {"model": "gpt-6-luna", "messages": messages, "max_completion_tokens": max_output_tokens, "timeout": 45.0}
    if json_schema:
        kwargs["response_format"] = {"type": "json_schema", "json_schema": json_schema}
    return await client.chat.completions.create(**kwargs)


def call_llm(messages, purpose, max_output_tokens, json_schema=None):
    """Call the course-configured model once, with cache and budget guards."""
    if purpose not in VALID_PURPOSES:
        raise ValueError(f"Invalid LLM purpose '{purpose}'.")
    if not isinstance(messages, list) or not messages:
        raise ValueError("LLM messages must be a non-empty list.")
    if max_output_tokens <= 0:
        raise ValueError("max_output_tokens must be positive.")

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")
    state = load_key_state(ROOT)
    # The course workspace stores its shared .env above this nested project.
    # Project-root and immediate-parent lookup still win when either contains a key.
    if not state.available:
        state = load_key_state(ROOT.parents[2])
    if not state.available:
        raise NoKeyError(state.message)
    model = "gpt-6-luna"
    key = _cache_key(purpose, messages, model)
    cache_disabled = os.getenv("FAIRDRAW_DISABLE_CACHE") == "1"
    cache = {} if cache_disabled else _read_json(CACHE_FILE, {})
    if not cache_disabled and key in cache:
        output = cache[key]["output"]
        usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
        _record_call(True, usage)
        append_usage(purpose, model, 0, 0, 0, 0.0, True)
        return LLMResponse(output, usage, True)

    _check_limits()
    provider_client = AsyncOpenAI(
        api_key=state.api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-cache-force-refresh": "true"},
    )
    started = time.perf_counter()
    try:
        response = asyncio.run(_request(provider_client, messages, max_output_tokens, json_schema))
    except (ConnectionError, TimeoutError, OSError):
        response = asyncio.run(_request(provider_client, messages, max_output_tokens, json_schema))
    message = response.choices[0].message.content
    try:
        output = json.loads(message)
    except (TypeError, json.JSONDecodeError):
        output = message
    response_usage = response.usage
    global _RAW_USAGE_PRINTED
    if not _RAW_USAGE_PRINTED:
        print(f"Raw provider usage object (development sample): {response_usage!r}")
        _RAW_USAGE_PRINTED = True
    usage = {
        "input_tokens": int(getattr(response_usage, "prompt_tokens", 0) or 0),
        "cached_input_tokens": int(getattr(response_usage, "prompt_tokens_details", None).cached_tokens or 0) if getattr(response_usage, "prompt_tokens_details", None) else 0,
        "output_tokens": int(getattr(response_usage, "completion_tokens", 0) or 0),
    }
    if not cache_disabled:
        cache[key] = {"purpose": purpose, "model": model, "output": output}
        _write_json(CACHE_FILE, cache)
    _record_call(False, usage)
    append_usage(purpose, model, usage["input_tokens"], usage["cached_input_tokens"], usage["output_tokens"], time.perf_counter() - started, False)
    return LLMResponse(output, usage, False)
