"""Deterministic, seeded candidate generation and draw comparison helpers."""

from __future__ import annotations

import random
from math import ceil

from . import config as default_config
from .cost import total_cost
from .metrics import pair_weights, repeat_score, strength_gap
from .models import DrawResult


def _validate(attendees: list[str], roster, settings) -> None:
    roster_names = {player.name for player in roster}
    if len(attendees) != len(set(attendees)):
        raise ValueError("Attendees must not contain duplicate names")
    unknown = sorted(set(attendees) - roster_names)
    if unknown:
        raise ValueError(f"Attendees not found in roster: {', '.join(unknown)}")
    minimum = settings.NUM_TEAMS * settings.MIN_PLAYERS_PER_TEAM
    if len(attendees) < minimum:
        raise ValueError(f"At least {minimum} attendees are required for {settings.NUM_TEAMS} teams")


def _split(players: list[str], rng: random.Random, settings) -> dict[str, list[str]]:
    order = list(players)
    rng.shuffle(order)
    base, extras = divmod(len(order), settings.NUM_TEAMS)
    team_order = list(range(settings.NUM_TEAMS))
    rng.shuffle(team_order)
    sizes = [base] * settings.NUM_TEAMS
    for index in team_order[:extras]:
        sizes[index] += 1
    teams = {}
    cursor = 0
    for index, size in enumerate(sizes):
        teams[settings.TEAM_NAMES[index]] = order[cursor:cursor + size]
        cursor += size
    return teams


def _score(teams, roster, history, settings, use_balance, use_memory):
    cost = total_cost(teams, roster, history, settings)
    if not use_balance:
        cost["strength"] = cost["top"] = cost["keeper"] = 0.0
    if not use_memory:
        cost["repeat"] = 0.0
    cost["total"] = settings.W_STRENGTH * cost["strength"] + settings.W_TOP * cost["top"] + settings.W_REPEAT * cost["repeat"] + settings.W_KEEPER * cost["keeper"]
    return cost


def draw(attendees, roster, history, config=default_config, seed=0, attempt_index=1, use_balance=True, use_memory=True):
    """Generate, score, and seed-select a reproducible team split."""
    attendees = list(attendees)
    _validate(attendees, roster, config)
    players = sorted(attendees)
    rng = random.Random(seed)
    candidates = []
    seen = set()
    for _ in range(config.CANDIDATES):
        teams = _split(players, rng, config)
        signature = tuple(tuple(teams[name]) for name in config.TEAM_NAMES[:config.NUM_TEAMS])
        if signature in seen:
            continue
        seen.add(signature)
        cost = _score(teams, roster, history, config, use_balance, use_memory)
        candidates.append((cost["total"], signature, teams, cost))
    if not candidates:
        raise ValueError("No candidate team splits could be generated")
    candidates.sort(key=lambda item: (item[0], item[1]))
    pool = candidates[: min(config.TOP_POOL, len(candidates))]
    chosen_index = 0 if not use_balance and not use_memory else rng.randrange(len(pool))
    _, _, teams, cost = pool[chosen_index]
    raw_repeat = repeat_score(teams, pair_weights(history, config.HISTORY_WINDOW, config.DECAY))
    metrics = {"strength_gap": strength_gap(teams, {player.name: player.rating for player in roster}), "repeat_score": raw_repeat, "top_cost": cost["top"], "keeper_cost": cost["keeper"]}
    return DrawResult(teams=teams, cost=cost, metrics=metrics, pool_rank=chosen_index + 1, seed=seed, engine_version=config.ENGINE_VERSION, attempt_index=attempt_index)


def random_baseline(attendees, roster, history, config=default_config, samples=500, seed=0):
    """Return metric distributions from pure random draws using one seeded stream."""
    rng = random.Random(seed)
    strengths, repeats = [], []
    for _ in range(samples):
        result = draw(attendees, roster, history, config, rng.randrange(2**63), use_balance=False, use_memory=False)
        strengths.append(strength_gap(result.teams, {player.name: player.rating for player in roster}))
        repeats.append(repeat_score(result.teams, pair_weights(history, config.HISTORY_WINDOW, config.DECAY)))
    return {"strength_gap": strengths, "repeat_score": repeats}


def percentile(result, baseline):
    """Return the share of baseline values strictly beaten by the chosen result."""
    return {metric: sum(value > result.metrics[metric] for value in values) / len(values) if values else 0.0 for metric, values in baseline.items()}
