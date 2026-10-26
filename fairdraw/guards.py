"""Small, auditable guards for untrusted chat and organizer text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class DefenseEvent:
    type: str
    message_index: int | None
    matched_pattern: str | None
    action_taken: str


_PATTERNS = (
    ("ignore previous instructions", re.compile(r"ignore\s+(all\s+)?(?:previous|your\s+instructions)|disregard\s+(the\s+)?system", re.I)),
    ("prompt extraction", re.compile(r"reveal\s+(the\s+)?(system\s+)?prompt|show\s+your\s+instructions", re.I)),
    ("role spoofing", re.compile(r"(?:^|\b)(system|developer|assistant)\s*:\s*", re.I)),
    ("tool injection", re.compile(r"(?:call|run|execute)\s+(?:a\s+)?(?:tool|function)|approve_payment|send_email", re.I)),
)


def sanitize_text(value: str | None, max_length: int, *, field: str = "text") -> tuple[str, list[DefenseEvent]]:
    original = str(value or "")
    cleaned = "".join(char for char in original if char in "\n\t" or ord(char) >= 32)
    events: list[DefenseEvent] = []
    if cleaned != original:
        events.append(DefenseEvent("sanitized_text", None, field, "control characters removed"))
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
        events.append(DefenseEvent("text_truncated", None, field, f"capped at {max_length} characters"))
    return cleaned, events


def sanitize_chat(text: str | None) -> tuple[str, list[DefenseEvent]]:
    return sanitize_text(text, config.MAX_TOTAL_CHARS, field="chat")


def sanitize_organizer_note(note: str | None) -> tuple[str, list[DefenseEvent]]:
    return sanitize_text(note, 240, field="organizer_note")


def detect_injection(text: str, message_index: int | None = None) -> list[DefenseEvent]:
    """Log suspicious patterns; the detector is not the security boundary."""
    return [DefenseEvent("injection_pattern", message_index, label, "logged; content remains untrusted data") for label, pattern in _PATTERNS if pattern.search(text)]
