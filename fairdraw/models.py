"""Validated data models used by the fair-draw application."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Player(BaseModel):
    name: str
    rating: int = Field(ge=1, le=10)
    keeper: bool = False
    aliases: list[str] = Field(default_factory=list)


class Night(BaseModel):
    date: date
    teams: dict[str, list[str]]


class DrawResult(BaseModel):
    teams: dict[str, list[str]]
    cost: dict[str, float]
    metrics: dict[str, object]
    pool_rank: int
    seed: int
    engine_version: str
    attempt_index: int


class Receipt(BaseModel):
    engine_version: str
    seed: int
    attempt_index: int
    timestamp: str
    attendees: list[str]
    ratings: dict[str, int] | None = None
    history: list[dict] | None = None
    config: dict
    teams: dict[str, list[str]]
    metrics: dict[str, object]
    inputs_hash: str

