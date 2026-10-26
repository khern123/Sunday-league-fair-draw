"""Code-only parsing and safety limits for exported group chats."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from . import config


@dataclass(frozen=True)
class Message:
    index: int
    sender: str
    timestamp: datetime
    text: str


@dataclass(frozen=True)
class SkippedLine:
    line_number: int
    line: str
    reason: str


@dataclass(frozen=True)
class ChatParseResult:
    messages: list[Message]
    skipped: list[SkippedLine]
    truncated: bool = False
    truncated_messages: int = 0
    truncated_characters: int = 0


_WHATSAPP = re.compile(r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<time>\d{1,2}:\d{2})\s+-\s+(?P<sender>[^:]+):\s?(?P<text>.*)$")
_BRACKET = re.compile(r"^\[(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{1,2}:\d{2})\]\s+(?P<sender>[^:]+):\s?(?P<text>.*)$")


def _timestamp(match: re.Match) -> datetime:
    raw = f"{match.group('date')} {match.group('time')}"
    for fmt in ("%m/%d/%y %H:%M", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    raise ValueError("unsupported timestamp")


def _system(sender: str, text: str) -> bool:
    value = f"{sender}: {text}".casefold()
    return sender.casefold() in {"system", "whatsapp"} or "messages are end-to-end encrypted" in value or "created this group" in value or "added" in value and "to the group" in value


def parse_chat(text: str, only_after: datetime | None = None) -> ChatParseResult:
    """Parse WhatsApp/bracket exports; continuation lines attach to the prior message."""
    messages: list[Message] = []
    skipped: list[SkippedLine] = []
    current: dict | None = None
    total_chars = 0
    truncated = False
    truncated_messages = 0
    truncated_characters = 0

    for line_number, raw_line in enumerate(str(text).splitlines(), 1):
        line = raw_line.rstrip("\r")
        match = _WHATSAPP.match(line) or _BRACKET.match(line)
        if match:
            if current is not None:
                current["text"] = "\n".join(current["parts"])
                if not _system(current["sender"], current["text"]):
                    stamp = current["timestamp"]
                    if only_after is None or stamp > only_after:
                        value = current["text"]
                        if len(value) > config.MAX_CHARS_PER_MESSAGE:
                            truncated = True; truncated_messages += 1; truncated_characters += len(value) - config.MAX_CHARS_PER_MESSAGE
                            value = value[:config.MAX_CHARS_PER_MESSAGE]
                        total_chars += len(value)
                        if total_chars <= config.MAX_TOTAL_CHARS:
                            messages.append(Message(len(messages), current["sender"], stamp, value))
                        else:
                            truncated = True; truncated_messages += 1; skipped.append(SkippedLine(current["line"], value, "total character limit"))
                else:
                    skipped.append(SkippedLine(current["line"], current["text"], "system message"))
            try:
                stamp = _timestamp(match)
            except ValueError:
                skipped.append(SkippedLine(line_number, line, "invalid timestamp")); current = None; continue
            current = {"line": line_number, "sender": match.group("sender").strip(), "timestamp": stamp, "parts": [match.group("text")]}
        elif current is not None and line.strip():
            current["parts"].append(line)
        elif line.strip():
            skipped.append(SkippedLine(line_number, line, "not a supported message header"))

    if current is not None:
        current["text"] = "\n".join(current["parts"])
        if not _system(current["sender"], current["text"]):
            stamp = current["timestamp"]
            if only_after is None or stamp > only_after:
                value = current["text"]
                if len(value) > config.MAX_CHARS_PER_MESSAGE:
                    truncated = True; truncated_messages += 1; truncated_characters += len(value) - config.MAX_CHARS_PER_MESSAGE; value = value[:config.MAX_CHARS_PER_MESSAGE]
                if total_chars + len(value) <= config.MAX_TOTAL_CHARS:
                    messages.append(Message(len(messages), current["sender"], stamp, value))
                else:
                    truncated = True; truncated_messages += 1; skipped.append(SkippedLine(current["line"], value, "total character limit"))
        else:
            skipped.append(SkippedLine(current["line"], current["text"], "system message"))

    if len(messages) > config.MAX_MESSAGES_PER_RUN:
        truncated = True; truncated_messages += len(messages) - config.MAX_MESSAGES_PER_RUN; messages = messages[:config.MAX_MESSAGES_PER_RUN]
    return ChatParseResult(messages, skipped, truncated, truncated_messages, truncated_characters)
