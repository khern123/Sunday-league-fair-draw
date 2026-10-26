"""Measure uncached token usage for the sample attendance + announcement flow."""
from __future__ import annotations
import argparse, json, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fairdraw import config, llm_client
from fairdraw.data_io import load_roster
from fairdraw.pipeline import run_attendance_pipeline
from fairdraw.draw import draw
from fairdraw.receipt import build_public_receipt
from fairdraw.announce_agent import create_announcement

ROOT = Path(__file__).resolve().parents[1]

def _planned_calls(chat: str) -> int:
    return (len(chat.splitlines()) + 24) // 25 + 1

def _refuse(runs, calls, reason):
    out = ROOT / "results"; out.mkdir(exist_ok=True)
    payload = {"status": "refused", "runs": runs, "calls_per_run": calls, "planned_calls": runs * calls, "reason": reason}
    (out / "token_runs.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out / "token_runs.md").write_text("# Token measurement\n\n**Status: REFUSED before any model call.**\n\n" + reason + "\n", encoding="utf-8")
    print(f"Calls planned before running: {runs * calls} ({calls} per run).")
    print(reason)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--runs", type=int, default=10); args = parser.parse_args()
    if args.runs <= 0: raise SystemExit("--runs must be positive")
    chat = (ROOT / "data/sample_chat.txt").read_text(encoding="utf-8")
    calls = _planned_calls(chat); total = args.runs * calls
    counters = llm_client._read_json(llm_client.COUNTER_FILE, {"session": 0, "daily": 0})
    session_used, daily_used = int(counters.get("session", 0)), int(counters.get("daily", 0))
    if calls > config.MAX_LLM_CALLS_PER_RUN:
        return _refuse(args.runs, calls, f"Refused: one run needs {calls} calls, above the per-run limit of {config.MAX_LLM_CALLS_PER_RUN}.")
    if session_used + total > config.SESSION_CALL_BUDGET:
        return _refuse(args.runs, calls, f"Refused: {total} calls are planned, but only {max(0, config.SESSION_CALL_BUDGET-session_used)} session calls remain (budget {config.SESSION_CALL_BUDGET}, already used {session_used}).")
    if daily_used + total > config.DAILY_CALL_BUDGET:
        return _refuse(args.runs, calls, f"Refused: {total} calls would exceed the daily budget of {config.DAILY_CALL_BUDGET}.")
    import os; os.environ["FAIRDRAW_DISABLE_CACHE"] = "1"
    roster = load_roster("sample_roster.csv", ROOT / "data"); attendees = [p.name for p in roster]; records = []
    for run in range(1, args.runs + 1):
        started = time.perf_counter(); before = llm_client.get_run_totals(); result = run_attendance_pipeline(chat, roster)
        draw_result = draw(attendees, roster, [], config, seed=48000 + run, attempt_index=run)
        create_announcement(build_public_receipt(draw_result, attendees, roster, [], config), "Kickoff tonight.")
        after = llm_client.get_run_totals()
        records.append({"run": run, **{k: after.get(k, 0)-before.get(k, 0) for k in ("input_tokens", "cached_input_tokens", "output_tokens", "calls", "cache_hits")}, "latency_seconds": round(time.perf_counter()-started, 4), "estimated_cost": None})
    stats = {k: {"mean": statistics.fmean(r[k] for r in records), "min": min(r[k] for r in records), "max": max(r[k] for r in records)} for k in records[0] if k != "run" and isinstance(records[0][k], (int, float))}
    summary = {"status": "completed", "runs": args.runs, "calls_per_run": calls, "provider_cached_token_count_runs": sum(r["cached_input_tokens"] > 0 for r in records), "per_run": records, "statistics": stats}
    out = ROOT / "results"; out.mkdir(exist_ok=True); (out / "token_runs.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# Token measurement", "", f"Runs: {args.runs}", f"Calls per run: {calls}", f"Runs with provider cached-token count > 0: {summary['provider_cached_token_count_runs']}", "", "| Metric | Mean | Min | Max |", "|---|---:|---:|---:|"] + [f"| {k} | {v['mean']:.2f} | {v['min']:.2f} | {v['max']:.2f} |" for k,v in stats.items()] + ["| estimated_cost | prices not set | prices not set | prices not set |"]
    (out / "token_runs.md").write_text("\n".join(lines) + "\n", encoding="utf-8"); print("\n".join(lines))
if __name__ == "__main__": main()
