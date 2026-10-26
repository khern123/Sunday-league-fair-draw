"""Safe, compact run traces for the organizer UI."""
from __future__ import annotations
import json, time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def record(step, component, kind, input_summary, output_summary, status="ok", tokens=None, started=None):
    return {"step":step,"component":component,"type":kind,"input_summary":str(input_summary)[:180],"output_summary":str(output_summary)[:180],"tokens":tokens or {},"duration_seconds":round(time.perf_counter()-started,4) if started else 0.0,"status":status}

def save_trace(records):
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path=ROOT/"results"/"traces"/f"trace_{stamp}.json"; path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"created_at":stamp,"steps":records},indent=2),encoding="utf-8")
    return path
