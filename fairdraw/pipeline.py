"""Stage 5 attendance pipeline orchestration."""

from __future__ import annotations

from datetime import datetime

from .attendance_agent import AttendanceResult, extract_attendance
from .chat_splitter import ChatParseResult, parse_chat
from .claims import ClaimsResult, build_proposals
from .models import Player
from .usage_log import get_run_totals
from .guards import detect_injection, sanitize_chat
from .verifier import verify_claims
from .trace import ROOT, record, save_trace
import time


def run_attendance_pipeline(chat_text: str, roster: list[Player], only_after: datetime | None = None, batch_size: int = 25):
    """Parse chat, extract claims, and build organizer proposals in one call."""
    before = get_run_totals()
    trace=[]; started=time.perf_counter()
    safe_chat, guard_events = sanitize_chat(chat_text)
    parsed: ChatParseResult = parse_chat(safe_chat, only_after=only_after)
    trace.append(record(1,"Chat splitter","code",f"chat input with {len(str(chat_text).splitlines())} lines",f"{len(parsed.messages)} messages, {len(parsed.skipped)} skipped", "flagged" if parsed.skipped or parsed.truncated else "ok", started=started))
    for message in parsed.messages:
        guard_events.extend(detect_injection(message.text, message.index))
    aliases = {player.name: player.aliases for player in roster}
    attendance: AttendanceResult = extract_attendance(parsed.messages, [player.name for player in roster], aliases, batch_size=batch_size)
    trace.append(record(2,"Attendance agent","LLM agent",f"{len(parsed.messages)} messages in batches of {batch_size}",f"{len(attendance.claims)} claims, {len(attendance.failed_batches)} failed batches", "flagged" if attendance.failed_batches else "ok", tokens={"input":0,"cached_input":0,"output":0}, started=started))
    claim_check = verify_claims(attendance.claims, parsed.messages)
    trace.append(record(3,"Claim resolver","code",f"{len(claim_check.claims)} verified candidate claims",f"{len(proposals.rows) if 'proposals' in locals() else 0} proposal rows", "ok", started=started))
    proposals: ClaimsResult = build_proposals(claim_check.claims, parsed.messages, roster)
    trace[-1]["output_summary"] = f"{len(proposals.rows)} proposal rows, {len(proposals.defense_events)} flags"
    trace.append(record(4,"Claim verifier","verifier",f"{len(attendance.claims)} extracted claims",f"{len(claim_check.claims)} retained, {len(claim_check.events)} dropped", "flagged" if claim_check.events else "ok", started=started))
    after = get_run_totals()
    token_totals = {key: after.get(key, 0) - before.get(key, 0) for key in ("input_tokens", "cached_input_tokens", "output_tokens", "calls", "cache_hits")}
    token_totals["estimated_cost"] = None if after.get("estimated_cost") is None or before.get("estimated_cost") is None else after["estimated_cost"] - before["estimated_cost"]
    trace.append(record(5,"Organizer confirmation","organizer",f"{len(proposals.rows)} proposed rows", "awaiting organizer confirmation", "blocked", started=started))
    trace_path = save_trace(trace)
    return {
        "messages": parsed.messages,
        "skipped": parsed.skipped,
        "truncated": parsed.truncated,
        "truncated_messages": parsed.truncated_messages,
        "truncated_characters": parsed.truncated_characters,
        "claims": claim_check.claims,
        "proposed_attendance": proposals.rows,
        "defense_events": [*guard_events, *claim_check.events, *proposals.defense_events],
        "failed_batches": attendance.failed_batches,
        "token_totals": token_totals,
        "trace": trace,
        "trace_path": str(trace_path.relative_to(ROOT)),
    }
