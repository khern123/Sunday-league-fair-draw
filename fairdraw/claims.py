"""Turn extracted attendance claims into organizer-facing proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .attendance_agent import Claim
from .chat_splitter import Message
from .models import Player


@dataclass(frozen=True)
class ProposedAttendance:
    player: str | None
    proposed_status: str
    source: str
    evidence_snippet: str
    sender: str
    flag: str | None = None
    guest_name: str | None = None


@dataclass(frozen=True)
class DefenseEvent:
    message_index: int
    event: str
    detail: str


@dataclass(frozen=True)
class ClaimsResult:
    rows: list[ProposedAttendance]
    defense_events: list[DefenseEvent]
    pending_guests: list[str]


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _mass(value: str) -> bool:
    text = _norm(value)
    return text in {"everyone", "all", "all of us", "everyone in", "all of us are in", "i'm in for everyone", "im in for everyone"} or "for everyone" in text or "all of us" in text


def build_proposals(claims: Iterable[Claim], messages: Iterable[Message], roster: Iterable[Player]) -> ClaimsResult:
    """Resolve claims without fuzzy matching; self claims are the only automatic proposals."""
    message_by_index = {message.index: message for message in messages}
    players = list(roster)
    lookup: dict[str, str] = {}
    for player in players:
        lookup[_norm(player.name)] = player.name
        for alias in player.aliases:
            lookup[_norm(alias)] = player.name
    rows: list[ProposedAttendance] = []
    events: list[DefenseEvent] = []
    pending_guests: list[str] = []
    latest_self: dict[str, tuple[datetime, ProposedAttendance]] = {}

    for claim in claims:
        message = message_by_index.get(claim.message_index)
        if message is None:
            events.append(DefenseEvent(claim.message_index, "rejected", "claim references a message that is not present")); continue
        subject = claim.subject_text.strip()
        if _mass(subject) or _mass(claim.evidence_snippet):
            events.append(DefenseEvent(message.index, "rejected_mass_claim", "mass attendance claims require individual confirmation")); continue
        if _norm(subject) in {"self", "i", "me", "myself"}:
            resolved = lookup.get(_norm(message.sender))
            if resolved is None:
                events.append(DefenseEvent(message.index, "unrecognized_self", f"sender '{message.sender}' is not on the roster")); continue
            is_self = True
        else:
            resolved = lookup.get(_norm(subject))
            is_self = resolved is not None and _norm(resolved) == _norm(message.sender)
        if claim.status == "guest_in":
            guest = (claim.guest_name or subject).strip()
            if guest and _norm(guest) not in lookup:
                pending_guests.append(guest)
                rows.append(ProposedAttendance(guest, "in", "guest", claim.evidence_snippet, message.sender, "pending organizer rating", guest))
            else:
                events.append(DefenseEvent(message.index, "rejected_guest", "guest name is missing or already on the roster"))
            continue
        if resolved is None:
            rows.append(ProposedAttendance(None, "unknown", "self claim" if is_self else "third-party", claim.evidence_snippet, message.sender, "unrecognized name"))
            events.append(DefenseEvent(message.index, "unrecognized_name", f"could not resolve '{subject}'")); continue
        status = "in" if claim.status == "late" else claim.status
        flag = "late" if claim.status == "late" else ("needs confirmation" if not is_self else None)
        row = ProposedAttendance(resolved, status, "self claim" if is_self else "third-party", claim.evidence_snippet, message.sender, flag)
        if is_self:
            prior = latest_self.get(resolved)
            if prior is None or message.timestamp >= prior[0]:
                latest_self[resolved] = (message.timestamp, row)
        else:
            rows.append(row); events.append(DefenseEvent(message.index, "third_party_confirmation", f"claim about {resolved} requires organizer confirmation"))

    rows.extend(row for _, row in sorted(latest_self.values(), key=lambda item: item[0]))
    return ClaimsResult(rows, events, list(dict.fromkeys(pending_guests)))
