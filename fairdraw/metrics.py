"""Pure fairness metrics for candidate team splits."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from math import ceil
from typing import Iterable


def team_average_ratings(teams: dict[str, list[str]], ratings: dict[str, int]) -> dict[str, float]:
    """Return each team's mean rating: sum(player ratings) / team size."""
    return {name: sum(ratings[player] for player in players) / len(players) for name, players in teams.items()}


def strength_gap(teams: dict[str, list[str]], ratings: dict[str, int]) -> float:
    """Return max team average rating minus min team average rating."""
    averages = team_average_ratings(teams, ratings).values()
    return max(averages) - min(averages) if averages else 0.0


def size_difference(teams: dict[str, list[str]]) -> int:
    """Return largest team size minus smallest team size."""
    sizes = [len(players) for players in teams.values()]
    return max(sizes) - min(sizes) if sizes else 0


def top_players(attendees: Iterable[str], ratings: dict[str, int], top_fraction: float) -> set[str]:
    """Return ceil(top_fraction * attendee count) highest-rated players, ties by name."""
    players = sorted(attendees, key=lambda player: (-ratings[player], player))
    return set(players[: ceil(top_fraction * len(players))])


def top_players_per_team(teams: dict[str, list[str]], top_set: set[str]) -> dict[str, int]:
    """Count members of top_set in each team."""
    return {team: sum(player in top_set for player in players) for team, players in teams.items()}


def keeper_counts(teams: dict[str, list[str]], keepers: set[str]) -> dict[str, int]:
    """Count keepers in each team."""
    return {team: sum(player in keepers for player in players) for team, players in teams.items()}


def pair_weights(history: list, window: int, decay: float) -> dict[tuple[str, str], float]:
    """Sum teammate nights for each unordered pair, weighted as decay ** age.

    The newest history item has age 0; older items have ages 1, 2, and so on.
    Only the newest ``window`` nights contribute.
    """
    weights: defaultdict[tuple[str, str], float] = defaultdict(float)
    for age, night in enumerate(reversed(history[-window:])):
        for players in night.teams.values():
            for left, right in combinations(sorted(players), 2):
                weights[(left, right)] += decay**age
    return dict(weights)


def repeat_score(teams: dict[str, list[str]], weights: dict[tuple[str, str], float]) -> float:
    """Return the mean pair weight among all same-team unordered pairs, or 0."""
    values = []
    for players in teams.values():
        values.extend(weights.get(pair, 0.0) for pair in combinations(sorted(players), 2))
    return sum(values) / len(values) if values else 0.0


def teammate_counts(history: list, window: int) -> dict[str, dict[str, int]]:
    """Return a player-to-teammate count matrix over the newest ``window`` nights."""
    counts: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    for night in history[-window:]:
        for players in night.teams.values():
            for player in players:
                for teammate in players:
                    if player != teammate:
                        counts[player][teammate] += 1
    return {player: dict(teammates) for player, teammates in counts.items()}
