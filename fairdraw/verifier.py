"""Code-owned verification gates for claims, draws, and announcements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .attendance_agent import Claim
from .chat_splitter import Message


ALLOWED_STATUSES = {"in", "out", "maybe", "late", "guest_in"}


@dataclass(frozen=True)
class VerificationEvent:
    type: str
    message_index: int | None
    detail: str


@dataclass(frozen=True)
class ClaimVerification:
    claims: list[Claim]
    events: list[VerificationEvent]


@dataclass(frozen=True)
class DrawVerification:
    valid: bool
    detail: str


def verify_claims(claims: Iterable[Claim], messages: Iterable[Message]) -> ClaimVerification:
    by_index = {message.index: message for message in messages}
    accepted, events = [], []
    allowed_fields = {"message_index", "subject_text", "status", "guest_name", "evidence_snippet"}
    for claim in claims:
        raw = claim.model_dump() if hasattr(claim, "model_dump") else claim.dict()
        index = raw.get("message_index")
        message = by_index.get(index)
        if set(raw) != allowed_fields:
            events.append(VerificationEvent("claim_dropped", index, "claim contains extra or missing fields")); continue
        if message is None:
            events.append(VerificationEvent("claim_dropped", index, "message index does not exist")); continue
        if raw.get("status") not in ALLOWED_STATUSES:
            events.append(VerificationEvent("claim_dropped", index, "status is not allowed")); continue
        evidence = raw.get("evidence_snippet", "")
        if not evidence or evidence not in message.text:
            events.append(VerificationEvent("claim_dropped", index, "evidence is not an exact substring of the message")); continue
        accepted.append(claim)
    return ClaimVerification(accepted, events)


def verify_draw(result, confirmed_attendees: list[str], attendance_confirmed: bool, rerun) -> DrawVerification:
    if not attendance_confirmed:
        return DrawVerification(False, "Attendance has not been confirmed.")
    teams = result.teams
    flattened = [name for players in teams.values() for name in players]
    expected = list(confirmed_attendees)
    if len(flattened) != len(set(flattened)) or set(flattened) != set(expected):
        return DrawVerification(False, "The teams do not contain each confirmed attendee exactly once.")
    sizes = [len(players) for players in teams.values()]
    if sizes and max(sizes) - min(sizes) > 1:
        return DrawVerification(False, "Team sizes differ by more than one player.")
    replay = rerun(result.seed, result.attempt_index)
    if replay.teams != teams:
        return DrawVerification(False, "Replaying the published seed did not reproduce the teams.")
    return DrawVerification(True, "The confirmed inputs and published seed reproduce these teams.")


def verify_announcement(text: str, attendees: Iterable[str], team_names: Iterable[str], allowed_numbers: Iterable[int | str]) -> DrawVerification:
    allowed_names = {str(value).casefold() for value in [*attendees, *team_names]}
    allowed_tokens = {token for name in allowed_names for token in re.findall(r"[a-z]+", name)}
    words = re.findall(r"\b[A-Z][A-Za-z]*(?:['-][A-Za-z]+)?\b", text)
    ignored = {"Draw", "The", "Seed", "Verify", "With", "Team", "Sunday", "League", "Fair", "Match", "App"}
    unknown = [word for word in words if word not in ignored and word.casefold() not in allowed_names and word.casefold() not in allowed_tokens]
    numbers = [int(value) for value in re.findall(r"\b\d+\b", text)]
    allowed = {int(value) for value in allowed_numbers}
    bad_numbers = [value for value in numbers if value not in allowed]
    if unknown or bad_numbers:
        detail = "Unknown names: " + ", ".join(unknown) if unknown else ""
        if bad_numbers: detail += ("; " if detail else "") + "Disallowed numbers: " + ", ".join(map(str, bad_numbers))
        return DrawVerification(False, detail)
    return DrawVerification(True, "Announcement contains only verified names and numbers.")
