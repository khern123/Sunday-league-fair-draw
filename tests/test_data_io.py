import json
from pathlib import Path

import pytest

from fairdraw.data_io import load_history, load_roster, save_history
from fairdraw.models import Night


def write_roster(path: Path, rows: str) -> None:
    path.write_text("name,rating,keeper,aliases\n" + rows, encoding="utf-8")


def test_sample_loaders_support_data_directory() -> None:
    root = Path(__file__).parents[1]
    assert len(load_roster("sample_roster.csv", root / "data")) == 14
    assert len(load_history("sample_history.json", root / "data")) == 6


def test_duplicate_names_are_rejected(tmp_path: Path) -> None:
    write_roster(tmp_path / "r.csv", "Alex,5,no,\nalex,6,no,\n")
    with pytest.raises(ValueError, match="duplicate player name"):
        load_roster(tmp_path / "r.csv")


def test_bad_ratings_are_rejected(tmp_path: Path) -> None:
    write_roster(tmp_path / "r.csv", "Alex,11,no,\n")
    with pytest.raises(ValueError, match="rating must be an integer"):
        load_roster(tmp_path / "r.csv")


def test_alias_collisions_are_rejected(tmp_path: Path) -> None:
    write_roster(tmp_path / "r.csv", "Alex,5,no,Sam\nSam,6,no,\n")
    with pytest.raises(ValueError, match="alias 'Sam' collides"):
        load_roster(tmp_path / "r.csv")


def test_history_save_is_readable_and_replaces_atomically(tmp_path: Path) -> None:
    target = tmp_path / "history.json"
    save_history([Night(date="2026-03-01", teams={"Team A": ["Alex"], "Team B": ["Sam"]})], target)
    assert load_history(target)[0].teams["Team A"] == ["Alex"]
    assert not list(tmp_path.glob(".*.tmp"))
    assert json.loads(target.read_text(encoding="utf-8"))[0]["date"] == "2026-03-01"
