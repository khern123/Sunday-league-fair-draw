"""Append-only usage records and live totals for model calls."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import config


ROOT = Path(__file__).resolve().parents[1]
USAGE_LOG = ROOT / "results" / "usage_log.jsonl"
RUN_STARTED = datetime.now(timezone.utc)


def _record_cost(input_tokens: int, cached_tokens: int, output_tokens: int):
    if any(value is None for value in (config.input_per_million, config.cached_input_per_million, config.output_per_million)):
        return None
    return ((input_tokens * config.input_per_million) + (cached_tokens * config.cached_input_per_million) + (output_tokens * config.output_per_million)) / 1_000_000


def append_usage(purpose: str, model: str, input_tokens: int, cached_input_tokens: int, output_tokens: int, latency_seconds: float, cache_hit: bool) -> dict:
    """Append one safe JSONL usage record and return it."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "purpose": purpose,
        "model": model,
        "input_tokens": int(input_tokens),
        "cached_input_tokens": int(cached_input_tokens),
        "output_tokens": int(output_tokens),
        "latency_seconds": round(float(latency_seconds), 4),
        "cache_hit": bool(cache_hit),
        "estimated_cost": _record_cost(input_tokens, cached_input_tokens, output_tokens),
    }
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def _records() -> list[dict]:
    if not USAGE_LOG.exists():
        return []
    records = []
    for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _totals(records: list[dict]) -> dict:
    return {
        "calls": len(records),
        "cache_hits": sum(record.get("cache_hit", False) for record in records),
        "input_tokens": sum(record.get("input_tokens", 0) for record in records),
        "cached_input_tokens": sum(record.get("cached_input_tokens", 0) for record in records),
        "output_tokens": sum(record.get("output_tokens", 0) for record in records),
        "latency_seconds": round(sum(record.get("latency_seconds", 0) for record in records), 4),
        "estimated_cost": None if any(record.get("estimated_cost") is None for record in records) else sum(record.get("estimated_cost", 0) for record in records),
    }


def get_run_totals() -> dict:
    """Return totals for the current process run."""
    return _totals([record for record in _records() if record.get("timestamp", "") >= RUN_STARTED.isoformat()])


def get_all_time_totals() -> dict:
    """Return totals across all records currently in the JSONL log."""
    return _totals(_records())


class UsageTracker:
    """UI-friendly live view over the append-only usage log."""

    def totals(self) -> dict:
        return get_run_totals()

    def all_time_totals(self) -> dict:
        return get_all_time_totals()
