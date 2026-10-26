from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from fairdraw import config
from fairdraw.cost import total_cost
from fairdraw.data_io import load_history, load_roster
from fairdraw.draw import draw, random_baseline
from fairdraw.metrics import repeat_score, strength_gap
from fairdraw.receipt import build_full_receipt, build_public_receipt, verify_full_receipt


ROOT = Path(__file__).parents[1]
ROSTER = load_roster("sample_roster.csv", ROOT / "data")
HISTORY = load_history("sample_history.json", ROOT / "data")


def settings(teams: int, minimum: int | None = None):
    values = {name: getattr(config, name) for name in dir(config) if name.isupper()}
    values["NUM_TEAMS"] = teams
    values["TEAM_NAMES"] = config.TEAM_NAMES[:teams]
    if minimum is not None:
        values["MIN_PLAYERS_PER_TEAM"] = minimum
    return SimpleNamespace(**values)


def attendees(count: int) -> list[str]:
    return [player.name for player in ROSTER[:count]]


@pytest.mark.parametrize("count", [10, 11, 12, 13])
@pytest.mark.parametrize("team_count", [2, 3, 4])
def test_team_sizes_differ_by_at_most_one(count: int, team_count: int) -> None:
    minimum = 2 if count < team_count * config.MIN_PLAYERS_PER_TEAM else config.MIN_PLAYERS_PER_TEAM
    result = draw(attendees(count), ROSTER, HISTORY, settings(team_count, minimum), seed=41)
    sizes = [len(players) for players in result.teams.values()]
    assert max(sizes) - min(sizes) <= 1


def test_attendees_are_unique_and_validation_errors_are_clear() -> None:
    result = draw(attendees(10), ROSTER, HISTORY, config, seed=1)
    assert sorted(sum(result.teams.values(), [])) == sorted(attendees(10))
    with pytest.raises(ValueError, match="unknown|not found"):
        draw(attendees(10) + ["Nobody"], ROSTER, HISTORY, config, seed=1)
    with pytest.raises(ValueError, match="duplicate"):
        draw(attendees(10) + [attendees(10)[0]], ROSTER, HISTORY, config, seed=1)
    with pytest.raises(ValueError, match="At least"):
        draw(attendees(5), ROSTER, HISTORY, config, seed=1)


def test_seed_and_input_order_are_deterministic() -> None:
    first = draw(attendees(12), ROSTER, HISTORY, config, seed=77)
    second = draw(list(reversed(attendees(12))), ROSTER, HISTORY, config, seed=77)
    assert first.teams == second.teams
    assert first.model_dump() == draw(attendees(12), ROSTER, HISTORY, config, seed=77).model_dump()


def test_different_seeds_change_the_draw() -> None:
    outputs = {tuple(tuple(team) for team in draw(attendees(12), ROSTER, HISTORY, config, seed=seed).teams.values()) for seed in range(20)}
    assert len(outputs) > 1


def test_draw_does_not_mutate_roster_or_ratings() -> None:
    before = deepcopy(ROSTER)
    draw(attendees(12), ROSTER, HISTORY, config, seed=3)
    assert ROSTER == before


def test_balance_statistical_result_is_better_than_random() -> None:
    balanced = [draw(attendees(14), ROSTER, HISTORY, config, seed=seed).metrics["strength_gap"] for seed in range(50)]
    random_result = random_baseline(attendees(14), ROSTER, HISTORY, config, samples=50, seed=9)
    print(f"balance average strength gap={sum(balanced) / len(balanced):.4f}; random average={sum(random_result['strength_gap']) / 50:.4f}")
    assert sum(balanced) / 50 < sum(random_result["strength_gap"]) / 50


def test_memory_statistical_result_is_better_than_memory_off() -> None:
    with_memory = [draw(attendees(14), ROSTER, HISTORY, config, seed=seed, use_memory=True).metrics["repeat_score"] for seed in range(50)]
    without_memory = [draw(attendees(14), ROSTER, HISTORY, config, seed=seed, use_memory=False).metrics["repeat_score"] for seed in range(50)]
    print(f"memory average repeat={sum(with_memory) / 50:.4f}; off average={sum(without_memory) / 50:.4f}")
    assert sum(with_memory) / 50 < sum(without_memory) / 50


def test_keeper_spread_statistical_result() -> None:
    two_keeper_roster = ROSTER
    balanced = 0
    for seed in range(50):
        result = draw(attendees(14), two_keeper_roster, HISTORY, config, seed=seed)
        counts = [sum(player in {"Cal", "Hugo"} for player in players) for players in result.teams.values()]
        balanced += counts == [1, 1]
    rate = balanced / 50
    print(f"keeper spread rate={rate:.2%} ({balanced}/50)")
    assert rate >= 0.90


def test_public_receipt_redacts_ratings_and_full_receipt_replays() -> None:
    result = draw(attendees(14), ROSTER, HISTORY, config, seed=123)
    full = build_full_receipt(result, attendees(14), ROSTER, HISTORY, config)
    public = build_public_receipt(result, attendees(14), ROSTER, HISTORY, config)
    assert "ratings" not in public
    assert all("rating" not in str(value).lower() for value in public.values())
    assert verify_full_receipt(full)["match"] is True
    changed_rating = deepcopy(full)
    changed_rating["ratings"]["Ari"] = 3
    assert verify_full_receipt(changed_rating)["match"] is False
    changed_seed = deepcopy(full)
    changed_seed["seed"] += 1
    assert verify_full_receipt(changed_seed)["match"] is False
