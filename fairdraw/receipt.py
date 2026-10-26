"""Tamper-evident full receipts and safe public receipts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from .draw import draw


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _input_snapshot(attendees, roster, history, config):
    return {
        "attendees": sorted(attendees),
        "ratings": {player.name: player.rating for player in roster},
        "keepers": sorted(player.name for player in roster if player.keeper),
        "history": [night.model_dump(mode="json") for night in history],
        "config": {name: getattr(config, name) for name in ("NUM_TEAMS", "TEAM_NAMES", "MIN_PLAYERS_PER_TEAM", "ENGINE_VERSION", "CANDIDATES", "TOP_POOL", "TOP_FRACTION", "HISTORY_WINDOW", "DECAY", "W_STRENGTH", "W_TOP", "W_REPEAT", "W_KEEPER")},
    }


def build_full_receipt(result, attendees, roster, history, config):
    """Build a receipt containing reproducibility inputs and their SHA-256 hash."""
    snapshot = _input_snapshot(attendees, roster, history, config)
    return {"engine_version": result.engine_version, "seed": result.seed, "attempt_index": result.attempt_index, "timestamp": datetime.now(timezone.utc).isoformat(), **snapshot, "teams": result.teams, "metrics": result.metrics, "cost": result.cost, "inputs_hash": hashlib.sha256(_canonical(snapshot).encode()).hexdigest()}


def build_public_receipt(result, attendees, roster, history, config):
    """Build a receipt that contains no ratings or history details."""
    full = build_full_receipt(result, attendees, roster, history, config)
    return {key: full[key] for key in ("engine_version", "seed", "attempt_index", "inputs_hash", "attendees", "teams")}


def verify_full_receipt(receipt):
    """Replay a full receipt's draw and return a match flag plus differences."""
    ratings = receipt["ratings"]
    roster = [{"name": name, "rating": rating, "keeper": name in receipt.get("keepers", []), "aliases": []} for name, rating in ratings.items()]
    from .models import Player, Night
    roster = [Player.model_validate(player) for player in roster]
    history = [Night.model_validate(item) for item in receipt["history"]]
    settings = SimpleNamespace(**receipt["config"])
    result = draw(receipt["attendees"], roster, history, settings, receipt["seed"], receipt["attempt_index"])
    differences = {}
    if result.teams != receipt["teams"]:
        differences["teams"] = {"expected": receipt["teams"], "actual": result.teams}
    if result.metrics != receipt["metrics"]:
        differences["metrics"] = {"expected": receipt["metrics"], "actual": result.metrics}
    return {"match": not differences, "diff": differences}
