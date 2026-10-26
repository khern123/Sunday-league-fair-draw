"""Weighted candidate-draw cost calculations."""

from __future__ import annotations

from . import config
from .metrics import (
    keeper_counts,
    pair_weights,
    repeat_score,
    strength_gap,
    top_players,
    top_players_per_team,
)


def total_cost(teams: dict[str, list[str]], roster, history: list, settings=config) -> dict[str, float]:
    """Return component costs and their weighted sum.

    Strength is the team-average gap. Top cost is the excess over the ideal
    ceil(total top players / team count) per team. Repeat cost is the mean
    recent teammate weight. Keeper cost is keeper-count spread, reduced by one
    when keepers cannot divide evenly, and floored at zero. Total is the sum of
    each component multiplied by its configured weight.
    """
    ratings = {player.name: player.rating for player in roster}
    keepers = {player.name for player in roster if player.keeper}
    top_set = top_players({player for players in teams.values() for player in players}, ratings, settings.TOP_FRACTION)
    top_counts = top_players_per_team(teams, top_set)
    ideal_top = (len(top_set) + len(teams) - 1) // len(teams)
    top = sum(max(0, count - ideal_top) for count in top_counts.values())
    keeper_values = list(keeper_counts(teams, keepers).values())
    keeper = max(keeper_values) - min(keeper_values) if keeper_values else 0
    if len(keepers) % len(teams) != 0:
        keeper = max(0, keeper - 1)
    repeat = repeat_score(teams, pair_weights(history, settings.HISTORY_WINDOW, settings.DECAY))
    strength = strength_gap(teams, ratings)
    total = settings.W_STRENGTH * strength + settings.W_TOP * top + settings.W_REPEAT * repeat + settings.W_KEEPER * keeper
    return {"strength": strength, "top": float(top), "repeat": repeat, "keeper": float(keeper), "total": total}
