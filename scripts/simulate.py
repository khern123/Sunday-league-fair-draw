"""Compare the three draw modes using the real fairdraw.draw engine."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fairdraw import config
from fairdraw.data_io import load_roster
from fairdraw.draw import draw
from fairdraw.models import Night


ROOT = Path(__file__).resolve().parents[1]
METHODS = {
    "A: random": (False, False),
    "B: balance": (True, False),
    "C: balance + memory": (True, True),
}
NIGHTS = 20
REPEATS = 50
ATTENDANCE_PROBABILITY = 0.8
CANDIDATES_PER_DRAW = 300


def settings():
    values = {name: getattr(config, name) for name in dir(config) if name.isupper()}
    values["CANDIDATES"] = CANDIDATES_PER_DRAW
    return SimpleNamespace(**values)


def _attendees(roster, rng):
    chosen = [player.name for player in roster if rng.random() < ATTENDANCE_PROBABILITY]
    while len(chosen) < 10:
        chosen = list(dict.fromkeys(chosen + [roster[rng.randrange(len(roster))].name]))
    return chosen


def _pair_counts(history):
    pairs = Counter()
    for night in history:
        for players in night.teams.values():
            for index, left in enumerate(players):
                for right in players[index + 1:]:
                    pairs[tuple(sorted((left, right)))] += 1
    return pairs


def _one_repeat(roster, master_seed):
    rng = random.Random(master_seed)
    results = {name: {"history": [], "strength": [], "top_same": [], "repeat": []} for name in METHODS}
    ratings = {player.name: player.rating for player in roster}
    top_two = [name for name, _ in sorted(ratings.items(), key=lambda item: (-item[1], item[0]))[:2]]
    top_three = [name for name, _ in sorted(ratings.items(), key=lambda item: (-item[1], item[0]))[:3]]
    cfg = settings()
    for night_index in range(NIGHTS):
        attendees = _attendees(roster, rng)
        night_seed = rng.randrange(2**63)
        for method, (use_balance, use_memory) in METHODS.items():
            history = results[method]["history"]
            result = draw(attendees, roster, history, cfg, seed=night_seed, attempt_index=night_index + 1, use_balance=use_balance, use_memory=use_memory)
            results[method]["strength"].append(float(result.metrics["strength_gap"]))
            teams_of_top = {team for team, players in result.teams.items() if any(player in players for player in top_two)}
            results[method]["top_same"].append(len(teams_of_top) == 1)
            results[method]["repeat"].append(float(result.metrics["repeat_score"]))
            history.append(Night(date=config_date(night_index), teams=result.teams))
    output = {}
    for method, values in results.items():
        pairs = _pair_counts(values["history"])
        teammate_sets = {player: set() for player in top_three}
        for night in values["history"]:
            for players in night.teams.values():
                for player in top_three:
                    if player in players:
                        teammate_sets[player].update(other for other in players if other != player)
        output[method] = {
            "average_strength_gap": statistics.fmean(values["strength"]),
            "top_two_same_team_pct": 100 * statistics.fmean(values["top_same"]),
            "maximum_pair_teammate_count": max(pairs.values(), default=0),
            "average_different_teammates_top3": statistics.fmean(len(value) for value in teammate_sets.values()),
            "average_repeat_score": statistics.fmean(values["repeat"]),
        }
    return output


def config_date(index):
    from datetime import date, timedelta
    return date(2026, 1, 1) + timedelta(days=index)


def run(roster_path: Path):
    roster = load_roster(roster_path.name, roster_path.parent)
    repeats = [_one_repeat(roster, seed) for seed in range(REPEATS)]
    try:
        display_roster = str(roster_path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        display_roster = "private roster (path omitted)"
    summary = {"settings": {"roster": display_roster, "nights_per_repeat": NIGHTS, "repeats": REPEATS, "attendance_probability": ATTENDANCE_PROBABILITY, "minimum_attendees": 10, "candidates_per_draw": CANDIDATES_PER_DRAW, "engine": "fairdraw.draw", "methods": {key: {"use_balance": value[0], "use_memory": value[1]} for key, value in METHODS.items()}}, "methods": {}}
    for method in METHODS:
        metrics = {key: [repeat[method][key] for repeat in repeats] for key in repeats[0][method]}
        summary["methods"][method] = {key: {"average": statistics.fmean(values), "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0} for key, values in metrics.items()}
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--roster", type=Path, default=ROOT / "data" / "sample_roster.csv")
    args = parser.parse_args()
    summary = run(args.roster)
    output = ROOT / "results"
    output.mkdir(exist_ok=True)
    (output / "simulation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = ["# Simulation summary", "", f"Roster: `{summary['settings']['roster']}`", "", "| Method | Strength gap | Top two same team | Max pair repeats | Avg top-3 teammates | Repeat score |", "|---|---:|---:|---:|---:|---:|"]
    for method, values in summary["methods"].items():
        def cell(key): return f"{values[key]['average']:.3f} ± {values[key]['std_dev']:.3f}"
        lines.append(f"| {method} | {cell('average_strength_gap')} | {cell('top_two_same_team_pct')}% | {cell('maximum_pair_teammate_count')} | {cell('average_different_teammates_top3')} | {cell('average_repeat_score')} |")
    (output / "simulation_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
