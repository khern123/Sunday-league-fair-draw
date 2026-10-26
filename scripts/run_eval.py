"""Evaluate the real attendance pipeline against reviewed labeled fixtures."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fairdraw.data_io import load_roster
from fairdraw.pipeline import run_attendance_pipeline

ROOT = Path(__file__).resolve().parents[1]


def _load():
    chat = (ROOT / "data/labeled/labeled_chat.txt").read_text(encoding="utf-8")
    claims = json.loads((ROOT / "data/labeled/expected_claims.json").read_text(encoding="utf-8"))["claims"]
    final = json.loads((ROOT / "data/labeled/expected_final_attendance.json").read_text(encoding="utf-8"))
    roster = load_roster("sample_roster.csv", ROOT / "data")
    expected_claims = {int(index): {(item["subject"], item["status"]) for item in values} for index, values in claims.items()}
    return chat, roster, expected_claims, final


def _scores(result, expected_claims, expected_final, roster):
    actual_by_index = {}
    for claim in result["claims"]:
        actual_by_index.setdefault(claim.message_index, set()).add((claim.subject_text, claim.status))
    expected_pairs = {(index, pair) for index, values in expected_claims.items() for pair in values}
    actual_pairs = {(index, pair) for index, values in actual_by_index.items() for pair in values}
    tp = len(expected_pairs & actual_pairs)
    precision = tp / len(actual_pairs) if actual_pairs else 1.0
    recall = tp / len(expected_pairs) if expected_pairs else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    rows = {row.player: row for row in result["proposed_attendance"] if row.player}
    final_correct = sum(bool(rows.get(name) and rows[name].proposed_status == status) for name, status in expected_final["players"].items())
    errors = []
    for index in sorted(set(expected_claims) | set(actual_by_index)):
        if expected_claims.get(index, set()) != actual_by_index.get(index, set()):
            errors.append({"message_index": index, "message": result["messages"][index].text if index < len(result["messages"]) else "", "expected": list(expected_claims.get(index, set())), "got": list(actual_by_index.get(index, set()))})
    third_party_wrong = sum(row.source == "third-party" and row.flag != "needs confirmation" for row in result["proposed_attendance"])
    # Mass claims are rejected by the resolver and therefore must never appear
    # in the retained claim list.  Defense events use the claims module's
    # ``event``/``message_index`` fields (not the guard event shape).
    mass_indices = {event.message_index for event in result["defense_events"] if getattr(event, "event", None) == "rejected_mass_claim"}
    mass_wrong = sum(claim.message_index in mass_indices for claim in result["claims"])
    injection_indices = {17, 18, 19}
    injection_changed = any(claim.message_index in injection_indices for claim in result["claims"])
    unknown_accepted = any(row.proposed_status != "unknown" and row.player is None for row in result["proposed_attendance"])
    return {"precision": precision, "recall": recall, "f1": f1, "final_accuracy": final_correct / len(expected_final["players"]), "third_party_or_mass_wrongly_auto_applied": third_party_wrong + mass_wrong, "injection_attempts_changed_attendance_or_rating": int(injection_changed), "unknown_names_wrongly_accepted": int(unknown_accepted), "errors": errors}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--runs", type=int, default=5); args = parser.parse_args()
    chat, roster, expected_claims, expected_final = _load()
    runs, errors = [], []
    for run in range(args.runs):
        started = time.perf_counter(); result = run_attendance_pipeline(chat, roster); elapsed = time.perf_counter() - started
        score = _scores(result, expected_claims, expected_final, roster); score.pop("errors", None)
        score.update({"run": run + 1, "latency_seconds": round(elapsed, 4), **result["token_totals"]}); runs.append(score)
        errors.extend({"run": run + 1, **error} for error in _scores(result, expected_claims, expected_final, roster)["errors"])
    numeric = [
        key for key in runs[0]
        if key != "run" and all(isinstance(row.get(key), (int, float)) for row in runs)
    ]
    averages = {key: statistics.fmean(row[key] for row in runs) for key in numeric}
    for key in runs[0]:
        if key not in averages and key != "run":
            averages[key] = None
    summary = {"runs": args.runs, "averages": averages, "per_run": runs}
    out = ROOT / "results"; out.mkdir(exist_ok=True)
    (out / "eval_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "eval_errors.md").write_text("# Evaluation errors\n\n" + ("\n".join(f"- Run {e['run']}, message {e['message_index']}: `{e['message']}`\n  - Expected: `{e['expected']}`\n  - Got: `{e['got']}`" for e in errors) if errors else "No wrong results recorded.\n"), encoding="utf-8")
    lines = ["# Attendance evaluation", "", f"Runs: {args.runs}", "", "| Metric | Average |", "|---|---:|"] + [f"| {key} | {value:.4f} |" if isinstance(value, (int, float)) else f"| {key} | not set |" for key, value in averages.items()]
    (out / "eval_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines)); print("\nErrors:", len(errors))


if __name__ == "__main__": main()
