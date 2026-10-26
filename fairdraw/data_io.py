"""Read and atomically write roster and history data."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

from .models import Night, Player


def _path(value, data_dir=None):
    path = Path(value)
    return Path(data_dir) / path if data_dir is not None and not path.is_absolute() else path


def load_roster(csv_path, data_dir=None):
    path = _path(csv_path, data_dir)
    players, names, aliases = [], {}, {}
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = csv.DictReader(row for row in handle if not row.lstrip().startswith("#"))
            if not rows.fieldnames or not {"name", "rating", "keeper", "aliases"}.issubset(rows.fieldnames):
                raise ValueError("Roster must have columns: name, rating, keeper, aliases")
            for line, row in enumerate(rows, 2):
                name = (row.get("name") or "").strip()
                key = name.casefold()
                if not name:
                    raise ValueError(f"Roster line {line}: name cannot be empty")
                if key in names:
                    raise ValueError(f"Roster line {line}: duplicate player name '{name}'")
                try:
                    rating = int((row.get("rating") or "").strip())
                except ValueError as exc:
                    raise ValueError(f"Roster line {line}: rating must be an integer from 1 to 10") from exc
                if not 1 <= rating <= 10:
                    raise ValueError(f"Roster line {line}: rating must be an integer from 1 to 10")
                keeper = (row.get("keeper") or "").strip().casefold()
                if keeper not in {"yes", "no"}:
                    raise ValueError(f"Roster line {line}: keeper must be yes or no")
                player_aliases = [a.strip() for a in (row.get("aliases") or "").split("|") if a.strip()]
                for alias in player_aliases:
                    alias_key = alias.casefold()
                    if alias_key == key or alias_key in names or alias_key in aliases:
                        raise ValueError(f"Roster line {line}: alias '{alias}' collides with a player name or alias")
                names[key] = name
                aliases.update({alias.casefold(): name for alias in player_aliases})
                players.append(Player(name=name, rating=rating, keeper=keeper == "yes", aliases=player_aliases))
        collisions = sorted(set(names) & set(aliases))
        if collisions:
            display = next(alias for player in players for alias in player.aliases if alias.casefold() == collisions[0])
            raise ValueError(f"alias '{display}' collides with a player name")
    except FileNotFoundError as exc:
        raise ValueError(f"Roster file not found: {path}") from exc
    return players


def load_history(json_path, data_dir=None):
    path = _path(json_path, data_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("History JSON must contain a list of nights")
        return [Night.model_validate(item) for item in payload]
    except FileNotFoundError as exc:
        raise ValueError(f"History file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid history data in {path}: {exc}") from exc


def save_history(nights, json_path, data_dir=None):
    path = _path(json_path, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump([night.model_dump(mode="json") for night in nights], handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
